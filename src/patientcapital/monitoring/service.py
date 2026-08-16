"""Application boundary for scheduled observation and append-only alerts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.application.services import get_portfolio
from patientcapital.contracts import (
    AlertAcknowledgementResponse,
    MonitorAlertListResponse,
    MonitorAlertResponse,
    MonitorRunListResponse,
    MonitorRunResponse,
)
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import MarketCandidate, MarketDataProvider
from patientcapital.monitoring.policy import (
    MONITOR_POLICY_VERSION,
    MonitorAssetObservation,
    MonitorTrigger,
    evaluate_monitor_triggers,
)
from patientcapital.persistence.models import (
    MonitorAlertAcknowledgementRecord,
    MonitorAlertRecord,
    MonitorRunRecord,
    PriceRecord,
)

_MONITOR_LOCK = 7_421_004


def _validate_time(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError(422, "INVALID_MONITOR_TIME", f"{name} must be timezone-aware")


def _run_key(scheduled_for: datetime) -> str:
    normalized = scheduled_for.astimezone(UTC).isoformat()
    digest = hashlib.sha256(f"{MONITOR_POLICY_VERSION}:{normalized}".encode()).hexdigest()
    return f"{MONITOR_POLICY_VERSION}:{digest}"


def _run_response(record: MonitorRunRecord) -> MonitorRunResponse:
    return MonitorRunResponse(
        id=record.id,
        policy_version=record.policy_version,
        scheduled_for=record.scheduled_for,
        observed_at=record.observed_at,
        provider=record.provider,
        status=cast(
            Literal["no_change", "alerts_created", "provider_error", "blocked"],
            record.status,
        ),
        error_code=record.error_code,
        alerts_created=record.alerts_created,
        created_at=record.created_at,
    )


def _ack_response(record: MonitorAlertAcknowledgementRecord) -> AlertAcknowledgementResponse:
    return AlertAcknowledgementResponse(
        id=record.id,
        alert_id=record.alert_id,
        created_at=record.created_at,
    )


def _alert_response(
    record: MonitorAlertRecord,
    acknowledgement: MonitorAlertAcknowledgementRecord | None,
) -> MonitorAlertResponse:
    return MonitorAlertResponse(
        id=record.id,
        monitor_run_id=record.monitor_run_id,
        kind=cast(
            Literal[
                "allocation_drift",
                "price_move",
                "research_expiring",
                "corporate_action_review",
            ],
            record.kind,
        ),
        severity=cast(Literal["info", "warning"], record.severity),
        asset_id=record.asset_id,
        title=record.title,
        message=record.message,
        evidence=record.evidence,
        created_at=record.created_at,
        acknowledgement=_ack_response(acknowledgement) if acknowledgement is not None else None,
    )


def _existing_run(session: Session, key: str) -> MonitorRunRecord | None:
    return session.scalar(select(MonitorRunRecord).where(MonitorRunRecord.idempotency_key == key))


def _research_policy_version(candidate: MarketCandidate) -> str | None:
    return candidate.research.policy_version if candidate.research is not None else None


def _error_run(
    session: Session,
    *,
    key: str,
    scheduled_for: datetime,
    observed_at: datetime,
    provider: str,
    code: str,
    detail: str,
    status: Literal["provider_error", "blocked"] = "provider_error",
) -> MonitorRunResponse:
    with session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MONITOR_LOCK})
        existing = _existing_run(session, key)
        if existing is not None:
            return _run_response(existing)
        record = MonitorRunRecord(
            id=uuid4(),
            idempotency_key=key,
            policy_version=MONITOR_POLICY_VERSION,
            scheduled_for=scheduled_for,
            observed_at=observed_at,
            provider=provider,
            status=status,
            error_code=code,
            alerts_created=0,
            input_snapshot={},
            result_snapshot={"error": {"code": code, "detail": detail}},
        )
        session.add(record)
        session.flush()
        return _run_response(record)


def _trigger_snapshot(trigger: MonitorTrigger) -> dict[str, object]:
    return {
        "kind": trigger.kind,
        "severity": trigger.severity,
        "asset_id": trigger.asset_id,
        "title": trigger.title,
        "message": trigger.message,
        "evidence": trigger.evidence,
    }


def run_monitor(
    session: Session,
    provider: MarketDataProvider,
    *,
    scheduled_for: datetime,
    observed_at: datetime,
) -> MonitorRunResponse:
    """Refresh held prices and persist threshold alerts; never create a transaction."""

    _validate_time(scheduled_for, name="scheduled_for")
    _validate_time(observed_at, name="observed_at")
    if observed_at < scheduled_for:
        raise ApplicationError(
            422, "INVALID_MONITOR_TIME", "observed_at cannot precede scheduled_for"
        )
    key = _run_key(scheduled_for)
    existing = _existing_run(session, key)
    if existing is not None:
        session.rollback()
        return _run_response(existing)
    session.rollback()

    try:
        get_portfolio(session)
    except ApplicationError as error:
        session.rollback()
        return _error_run(
            session,
            key=key,
            scheduled_for=scheduled_for,
            observed_at=observed_at,
            provider=provider.name,
            code=error.code,
            detail=error.message,
            status="blocked",
        )
    session.rollback()

    try:
        discovered = provider.discover(calculated_at=observed_at)
    except MarketDataError as error:
        return _error_run(
            session,
            key=key,
            scheduled_for=scheduled_for,
            observed_at=observed_at,
            provider=provider.name,
            code=error.code,
            detail=error.detail,
        )
    candidates: dict[str, MarketCandidate] = {}
    for candidate in discovered:
        if candidate.asset_id in candidates:
            return _error_run(
                session,
                key=key,
                scheduled_for=scheduled_for,
                observed_at=observed_at,
                provider=provider.name,
                code="MARKET_DATA_INVALID",
                detail=f"duplicate market candidate {candidate.asset_id}",
            )
        candidates[candidate.asset_id] = candidate

    with session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MONITOR_LOCK})
        existing = _existing_run(session, key)
        if existing is not None:
            return _run_response(existing)
        previous = get_portfolio(session)
        held = [asset for asset in previous.assets if asset.quantity > 0]
        missing = sorted(asset.asset_id for asset in held if asset.asset_id not in candidates)
        if missing:
            record = MonitorRunRecord(
                id=uuid4(),
                idempotency_key=key,
                policy_version=MONITOR_POLICY_VERSION,
                scheduled_for=scheduled_for,
                observed_at=observed_at,
                provider=provider.name,
                status="provider_error",
                error_code="UNSUPPORTED_MARKET_HOLDING",
                alerts_created=0,
                input_snapshot={"held_asset_ids": [asset.asset_id for asset in held]},
                result_snapshot={"missing_asset_ids": missing},
            )
            session.add(record)
            session.flush()
            return _run_response(record)

        for asset in held:
            candidate = candidates[asset.asset_id]
            session.add(
                PriceRecord(
                    id=uuid4(),
                    asset_id=asset.asset_id,
                    price=candidate.unit_price,
                    currency=candidate.currency,
                    as_of=candidate.price_as_of,
                    max_age_seconds=int(candidate.max_age.total_seconds()),
                    source=candidate.source_url,
                )
            )
        session.flush()
        current = get_portfolio(session)
        current_by_id = {asset.asset_id: asset for asset in current.assets}
        observations = tuple(
            MonitorAssetObservation(
                asset_id=asset.asset_id,
                quantity=asset.quantity,
                previous_price=asset.latest_price,
                current_price=current_by_id[asset.asset_id].latest_price,
                drift=current_by_id[asset.asset_id].drift,
                research=candidates[asset.asset_id].research,
            )
            for asset in held
        )
        triggers = evaluate_monitor_triggers(observations, calculated_at=observed_at)
        date_key = scheduled_for.date().isoformat()
        new_triggers: list[tuple[MonitorTrigger, str]] = []
        suppressed: list[str] = []
        for trigger in triggers:
            dedupe_key = (
                f"{MONITOR_POLICY_VERSION}:{date_key}:{trigger.kind}:{trigger.asset_id}"
            )
            known = session.scalar(
                select(MonitorAlertRecord.id).where(MonitorAlertRecord.dedupe_key == dedupe_key)
            )
            if known is None:
                new_triggers.append((trigger, dedupe_key))
            else:
                suppressed.append(dedupe_key)
        run_id = uuid4()
        status = "alerts_created" if new_triggers else "no_change"
        record = MonitorRunRecord(
            id=run_id,
            idempotency_key=key,
            policy_version=MONITOR_POLICY_VERSION,
            scheduled_for=scheduled_for,
            observed_at=observed_at,
            provider=provider.name,
            status=status,
            error_code=None,
            alerts_created=len(new_triggers),
            input_snapshot={
                "held_assets": [
                    {
                        "asset_id": item.asset_id,
                        "quantity": item.quantity,
                        "previous_price": str(item.previous_price),
                        "current_price": str(item.current_price),
                        "drift": str(item.drift),
                        "price_source": candidates[item.asset_id].source_url,
                        "price_as_of": candidates[item.asset_id].price_as_of.isoformat(),
                        "research_policy_version": _research_policy_version(
                            candidates[item.asset_id]
                        ),
                    }
                    for item in observations
                ]
            },
            result_snapshot={
                "triggers": [_trigger_snapshot(trigger) for trigger in triggers],
                "created_dedupe_keys": [dedupe_key for _, dedupe_key in new_triggers],
                "suppressed_dedupe_keys": suppressed,
            },
        )
        session.add(record)
        session.flush()
        for trigger, dedupe_key in new_triggers:
            session.add(
                MonitorAlertRecord(
                    id=uuid4(),
                    monitor_run_id=run_id,
                    dedupe_key=dedupe_key,
                    kind=trigger.kind,
                    severity=trigger.severity,
                    asset_id=trigger.asset_id,
                    title=trigger.title,
                    message=trigger.message,
                    evidence=trigger.evidence,
                )
            )
        session.flush()
        return _run_response(record)


def list_monitor_runs(session: Session, *, limit: int = 20) -> MonitorRunListResponse:
    if not 1 <= limit <= 100:
        raise ApplicationError(422, "INVALID_LIMIT", "limit must be between 1 and 100")
    records = session.scalars(
        select(MonitorRunRecord)
        .order_by(MonitorRunRecord.scheduled_for.desc(), MonitorRunRecord.id.desc())
        .limit(limit)
    )
    return MonitorRunListResponse(runs=[_run_response(record) for record in records])


def list_alerts(
    session: Session,
    *,
    include_acknowledged: bool = True,
    limit: int = 100,
) -> MonitorAlertListResponse:
    if not 1 <= limit <= 100:
        raise ApplicationError(422, "INVALID_LIMIT", "limit must be between 1 and 100")
    records = list(
        session.scalars(
            select(MonitorAlertRecord)
            .order_by(MonitorAlertRecord.created_at.desc(), MonitorAlertRecord.kind.desc())
            .limit(limit)
        )
    )
    alert_ids = [record.id for record in records]
    acknowledgements = {
        record.alert_id: record
        for record in session.scalars(
            select(MonitorAlertAcknowledgementRecord).where(
                MonitorAlertAcknowledgementRecord.alert_id.in_(alert_ids)
            )
        )
    }
    responses = [
        _alert_response(record, acknowledgements.get(record.id)) for record in records
    ]
    if not include_acknowledged:
        responses = [item for item in responses if item.acknowledgement is None]
    return MonitorAlertListResponse(alerts=responses)


def acknowledge_alert(
    session: Session, alert_id: UUID
) -> tuple[AlertAcknowledgementResponse, bool]:
    with session.begin():
        alert = session.get(MonitorAlertRecord, alert_id)
        if alert is None:
            raise ApplicationError(404, "ALERT_NOT_FOUND", "monitor alert was not found")
        existing = session.scalar(
            select(MonitorAlertAcknowledgementRecord).where(
                MonitorAlertAcknowledgementRecord.alert_id == alert_id
            )
        )
        if existing is not None:
            return _ack_response(existing), False
        record = MonitorAlertAcknowledgementRecord(id=uuid4(), alert_id=alert_id)
        session.add(record)
        session.flush()
        return _ack_response(record), True
