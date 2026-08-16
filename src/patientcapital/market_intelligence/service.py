"""Acquire immutable market snapshots from a bounded source-backed scanner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from patientcapital.domain.admission import (
    ADMISSION_POLICY_VERSION,
    AdmissionDimension,
    AdmissionGate,
    AdmissionStatus,
    AssetAdmissionProfile,
    evaluate_asset_admission,
)
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketDataProvider,
    MarketLiquidityEvidence,
    MarketScan,
    MarketScanProvider,
)
from patientcapital.persistence.models import (
    AssetAdmissionAssessmentRecord,
    AssetAdmissionRunRecord,
    IssuerEvidenceSnapshotRecord,
    MarketResearchSnapshotRecord,
)
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)
from patientcapital.research.provider import (
    IssuerEvidenceBatch,
    IssuerEvidenceProvider,
    IssuerEvidenceResult,
    IssuerIdentity,
    ReviewedIssuerCorpusProvider,
    deserialize_issuer_bundle,
    serialize_issuer_bundle,
)


@dataclass(frozen=True, slots=True)
class AcquiredMarketResearch:
    record: MarketResearchSnapshotRecord
    candidates: tuple[MarketCandidate, ...]
    mode: Literal["live", "cached"]
    admission_run: AssetAdmissionRunRecord
    profiles: dict[str, AssetAdmissionProfile]


def _decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _research_payload(research: DividendResearchEvidence) -> dict[str, object]:
    return {
        "schema_version": research.schema_version,
        "policy_version": research.policy_version,
        "scope": research.scope.value,
        "observed_at": research.observed_at.isoformat(),
        "max_age_seconds": int(research.max_age.total_seconds()),
        "reporting_period_end": (
            research.reporting_period_end.isoformat()
            if research.reporting_period_end is not None
            else None
        ),
        "profitable_years": research.profitable_years,
        "dividend_years": research.dividend_years,
        "payout_ratio_percent": (
            str(research.payout_ratio_percent)
            if research.payout_ratio_percent is not None
            else None
        ),
        "balance_sheet_status": research.balance_sheet_status.value,
        "governance_program_member": research.governance_program_member,
        "corporate_action_status": research.corporate_action_status.value,
        "summary": research.summary,
        "annual_dividend_per_share": (
            str(research.annual_dividend_per_share)
            if research.annual_dividend_per_share is not None
            else None
        ),
        "historical_dividend_yield_percent": (
            str(research.historical_dividend_yield_percent)
            if research.historical_dividend_yield_percent is not None
            else None
        ),
        "last_registry_close_date": (
            research.last_registry_close_date.isoformat()
            if research.last_registry_close_date is not None
            else None
        ),
        "listing_level": research.listing_level,
        "unknown_facts": list(research.unknown_facts),
        "citations": [
            {"kind": item.kind.value, "title": item.title, "url": item.url}
            for item in research.citations
        ],
    }


def _liquidity_payload(liquidity: MarketLiquidityEvidence) -> dict[str, object]:
    return {
        "policy_version": liquidity.policy_version,
        "observed_at": liquidity.observed_at.isoformat(),
        "max_age_seconds": int(liquidity.max_age.total_seconds()),
        "security_status": liquidity.security_status,
        "source_url": liquidity.source_url,
        "observations": [
            {
                "session_date": item.session_date.isoformat(),
                "turnover_rub": str(item.turnover_rub),
                "trades": item.trades,
                "bid": str(item.bid) if item.bid is not None else None,
                "offer": str(item.offer) if item.offer is not None else None,
            }
            for item in liquidity.observations
        ],
    }


def _gate_payload(gate: AdmissionGate) -> dict[str, object]:
    return {
        "gate_id": gate.gate_id,
        "status": gate.status.value,
        "reason_code": gate.reason_code,
        "observed_value": gate.observed_value,
        "unit": gate.unit,
        "threshold": gate.threshold,
        "source_url": gate.source_url,
        "observed_at": gate.observed_at.isoformat(),
        "valid_until": gate.valid_until.isoformat(),
        "material": gate.material,
    }


def _dimension_payload(dimension: AdmissionDimension) -> dict[str, object]:
    return {
        "policy_version": dimension.policy_version,
        "status": dimension.status.value,
        "reason_codes": list(dimension.reason_codes),
        "gates": [_gate_payload(item) for item in dimension.gates],
    }


def serialize_admission_profile(profile: AssetAdmissionProfile) -> dict[str, object]:
    return {
        "policy_version": profile.policy_version,
        "asset_id": profile.asset_id,
        "instrument_kind": profile.instrument_kind.value,
        "strategy_profile": profile.strategy_profile,
        "overall_status": profile.overall_status.value,
        "evaluated_at": profile.evaluated_at.isoformat(),
        "expires_at": profile.expires_at.isoformat(),
        "liquidity": _dimension_payload(profile.liquidity),
        "investment": _dimension_payload(profile.investment),
        "reason_codes": list(profile.reason_codes),
        "hard_kills": list(profile.hard_kills),
        "unknowns": list(profile.unknowns),
    }


def serialize_candidate(candidate: MarketCandidate) -> dict[str, object]:
    return {
        "asset_id": candidate.asset_id,
        "name": candidate.name,
        "kind": candidate.kind.value,
        "currency": candidate.currency,
        "lot_size": candidate.lot_size,
        "unit_price": str(candidate.unit_price),
        "price_as_of": candidate.price_as_of.isoformat(),
        "max_age_seconds": int(candidate.max_age.total_seconds()),
        "source_url": candidate.source_url,
        "classification_url": candidate.classification_url,
        "quote_kind": candidate.quote_kind,
        "turnover": str(candidate.turnover),
        "isin": candidate.isin,
        "maturity_date": (
            candidate.maturity_date.isoformat() if candidate.maturity_date is not None else None
        ),
        "yield_percent": (
            str(candidate.yield_percent) if candidate.yield_percent is not None else None
        ),
        "clean_price_percent": (
            str(candidate.clean_price_percent)
            if candidate.clean_price_percent is not None
            else None
        ),
        "face_value": str(candidate.face_value) if candidate.face_value is not None else None,
        "accrued_interest": (
            str(candidate.accrued_interest) if candidate.accrued_interest is not None else None
        ),
        "next_coupon_date": (
            candidate.next_coupon_date.isoformat()
            if candidate.next_coupon_date is not None
            else None
        ),
        "coupon_percent": (
            str(candidate.coupon_percent) if candidate.coupon_percent is not None else None
        ),
        "coupon_value": (
            str(candidate.coupon_value) if candidate.coupon_value is not None else None
        ),
        "research": _research_payload(candidate.research) if candidate.research else None,
        "issuer_evidence": (
            serialize_issuer_bundle(candidate.issuer_evidence)
            if candidate.issuer_evidence is not None
            else None
        ),
        "liquidity": (
            _liquidity_payload(candidate.liquidity) if candidate.liquidity is not None else None
        ),
    }


def _date(value: object | None):  # type: ignore[no-untyped-def]
    if value is None:
        return None
    from datetime import date

    return date.fromisoformat(str(value))


def _research_from_payload(payload: dict[str, object]) -> DividendResearchEvidence:
    raw_citations = cast(list[dict[str, object]], payload["citations"])
    return DividendResearchEvidence(
        schema_version=str(payload["schema_version"]),
        policy_version=str(payload["policy_version"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        max_age=timedelta(seconds=int(cast(int, payload["max_age_seconds"]))),
        reporting_period_end=_date(payload.get("reporting_period_end")),
        profitable_years=cast(int | None, payload.get("profitable_years")),
        dividend_years=int(cast(int, payload["dividend_years"])),
        payout_ratio_percent=_decimal(payload.get("payout_ratio_percent")),
        balance_sheet_status=BalanceSheetStatus(str(payload["balance_sheet_status"])),
        governance_program_member=cast(bool | None, payload.get("governance_program_member")),
        corporate_action_status=CorporateActionStatus(str(payload["corporate_action_status"])),
        summary=str(payload["summary"]),
        citations=tuple(
            ResearchCitation(
                kind=ResearchFactKind(str(item["kind"])),
                title=str(item["title"]),
                url=str(item["url"]),
            )
            for item in raw_citations
        ),
        scope=ResearchScope(str(payload["scope"])),
        annual_dividend_per_share=_decimal(payload.get("annual_dividend_per_share")),
        historical_dividend_yield_percent=_decimal(
            payload.get("historical_dividend_yield_percent")
        ),
        last_registry_close_date=_date(payload.get("last_registry_close_date")),
        listing_level=cast(int | None, payload.get("listing_level")),
        unknown_facts=tuple(cast(list[str], payload.get("unknown_facts", []))),
    )


def _liquidity_from_payload(payload: dict[str, object]) -> MarketLiquidityEvidence:
    observations = cast(list[dict[str, object]], payload["observations"])
    return MarketLiquidityEvidence(
        policy_version=str(payload["policy_version"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        max_age=timedelta(seconds=int(cast(int, payload["max_age_seconds"]))),
        security_status=str(payload["security_status"]),
        source_url=str(payload["source_url"]),
        observations=tuple(
            LiquidityObservation(
                session_date=_date(item["session_date"]),
                turnover_rub=Decimal(str(item["turnover_rub"])),
                trades=int(cast(int, item["trades"])),
                bid=_decimal(item.get("bid")),
                offer=_decimal(item.get("offer")),
            )
            for item in observations
        ),
    )


def _gate_from_payload(payload: dict[str, object]) -> AdmissionGate:
    return AdmissionGate(
        gate_id=str(payload["gate_id"]),
        status=AdmissionStatus(str(payload["status"])),
        reason_code=str(payload["reason_code"]),
        observed_value=(
            str(payload["observed_value"]) if payload.get("observed_value") is not None else None
        ),
        unit=str(payload["unit"]) if payload.get("unit") is not None else None,
        threshold=(str(payload["threshold"]) if payload.get("threshold") is not None else None),
        source_url=str(payload["source_url"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        valid_until=datetime.fromisoformat(str(payload["valid_until"])),
        material=bool(payload.get("material", True)),
    )


def _dimension_from_payload(payload: dict[str, object]) -> AdmissionDimension:
    gates = cast(list[dict[str, object]], payload["gates"])
    return AdmissionDimension(
        policy_version=str(payload["policy_version"]),
        status=AdmissionStatus(str(payload["status"])),
        gates=tuple(_gate_from_payload(item) for item in gates),
        reason_codes=tuple(cast(list[str], payload["reason_codes"])),
    )


def deserialize_admission_profile(payload: dict[str, object]) -> AssetAdmissionProfile:
    return AssetAdmissionProfile(
        policy_version=str(payload["policy_version"]),
        asset_id=str(payload["asset_id"]),
        instrument_kind=InstrumentKind(str(payload["instrument_kind"])),
        strategy_profile=str(payload["strategy_profile"]),
        overall_status=AdmissionStatus(str(payload["overall_status"])),
        evaluated_at=datetime.fromisoformat(str(payload["evaluated_at"])),
        expires_at=datetime.fromisoformat(str(payload["expires_at"])),
        liquidity=_dimension_from_payload(cast(dict[str, object], payload["liquidity"])),
        investment=_dimension_from_payload(cast(dict[str, object], payload["investment"])),
        reason_codes=tuple(cast(list[str], payload["reason_codes"])),
        hard_kills=tuple(cast(list[str], payload["hard_kills"])),
        unknowns=tuple(cast(list[str], payload["unknowns"])),
    )


def deserialize_candidate(payload: dict[str, object]) -> MarketCandidate:
    research_payload = payload.get("research")
    issuer_evidence_payload = payload.get("issuer_evidence")
    liquidity_payload = payload.get("liquidity")
    return MarketCandidate(
        asset_id=str(payload["asset_id"]),
        name=str(payload["name"]),
        kind=InstrumentKind(str(payload["kind"])),
        currency=str(payload["currency"]),
        lot_size=int(cast(int, payload["lot_size"])),
        unit_price=Decimal(str(payload["unit_price"])),
        price_as_of=datetime.fromisoformat(str(payload["price_as_of"])),
        max_age=timedelta(seconds=int(cast(int, payload["max_age_seconds"]))),
        source_url=str(payload["source_url"]),
        classification_url=str(payload["classification_url"]),
        quote_kind=str(payload["quote_kind"]),
        turnover=Decimal(str(payload["turnover"])),
        isin=str(payload["isin"]) if payload.get("isin") is not None else None,
        maturity_date=_date(payload.get("maturity_date")),
        yield_percent=_decimal(payload.get("yield_percent")),
        clean_price_percent=_decimal(payload.get("clean_price_percent")),
        face_value=_decimal(payload.get("face_value")),
        accrued_interest=_decimal(payload.get("accrued_interest")),
        next_coupon_date=_date(payload.get("next_coupon_date")),
        coupon_percent=_decimal(payload.get("coupon_percent")),
        coupon_value=_decimal(payload.get("coupon_value")),
        research=(
            _research_from_payload(cast(dict[str, object], research_payload))
            if research_payload is not None
            else None
        ),
        issuer_evidence=(
            deserialize_issuer_bundle(cast(dict[str, object], issuer_evidence_payload))
            if issuer_evidence_payload is not None
            else None
        ),
        liquidity=(
            _liquidity_from_payload(cast(dict[str, object], liquidity_payload))
            if liquidity_payload is not None
            else None
        ),
    )


def _scan(provider: MarketDataProvider, *, observed_at: datetime) -> MarketScan:
    if isinstance(provider, MarketScanProvider):
        return provider.scan(calculated_at=observed_at)
    candidates = provider.discover(calculated_at=observed_at)
    return MarketScan(
        policy_version="legacy-provider-scan-v1",
        observed_at=observed_at,
        candidates=candidates,
        universe_size=len(candidates),
        kind_counts={
            kind.value: sum(1 for item in candidates if item.kind is kind)
            for kind in InstrumentKind
        },
        enriched_count=sum(1 for item in candidates if item.research is not None),
    )


def _load_admission(
    session: Session, snapshot_id: object, issuer_evidence_set_hash: str
) -> tuple[AssetAdmissionRunRecord, dict[str, AssetAdmissionProfile]] | None:
    run = session.scalar(
        select(AssetAdmissionRunRecord)
        .where(
            AssetAdmissionRunRecord.market_snapshot_id == snapshot_id,
            AssetAdmissionRunRecord.policy_version == ADMISSION_POLICY_VERSION,
            AssetAdmissionRunRecord.issuer_evidence_set_hash == issuer_evidence_set_hash,
        )
        .order_by(AssetAdmissionRunRecord.evaluated_at.desc())
        .limit(1)
    )
    if run is None:
        return None
    records = session.scalars(
        select(AssetAdmissionAssessmentRecord)
        .where(AssetAdmissionAssessmentRecord.run_id == run.id)
        .order_by(AssetAdmissionAssessmentRecord.asset_id)
    ).all()
    profiles = {item.asset_id: deserialize_admission_profile(item.profile) for item in records}
    if len(profiles) != run.assessment_count:
        raise MarketDataError(
            "ADMISSION_SNAPSHOT_INCOMPLETE",
            "asset-admission assessment count does not match the immutable run",
        )
    return run, profiles


def _issuer_idempotency_key(result: IssuerEvidenceResult) -> str:
    payload = (
        result.identity.asset_id,
        result.identity.isin,
        result.status.value,
        result.provider,
        result.schema_version,
        result.bundle.evidence_hash if result.bundle is not None else None,
        result.error_code,
    )
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return f"issuer:{digest}"


def _acquire_issuer_batch(
    candidates: tuple[MarketCandidate, ...],
    provider: IssuerEvidenceProvider,
    *,
    observed_at: datetime,
) -> IssuerEvidenceBatch:
    identities = tuple(
        IssuerIdentity(item.asset_id, item.isin)
        for item in candidates
        if item.kind in {InstrumentKind.DIVIDEND_STOCK, InstrumentKind.PUBLIC_EQUITY}
        and item.isin is not None
    )
    return provider.acquire(identities=identities, observed_at=observed_at)


def _persist_issuer_batch(
    session: Session,
    batch: IssuerEvidenceBatch,
) -> dict[str, IssuerEvidenceSnapshotRecord]:
    records: dict[str, IssuerEvidenceSnapshotRecord] = {}
    for result in batch.results:
        key = _issuer_idempotency_key(result)
        record = session.scalar(
            select(IssuerEvidenceSnapshotRecord).where(
                IssuerEvidenceSnapshotRecord.idempotency_key == key
            )
        )
        if record is None:
            bundle = result.bundle
            record = IssuerEvidenceSnapshotRecord(
                id=uuid4(),
                idempotency_key=key,
                asset_id=result.identity.asset_id,
                isin=result.identity.isin,
                provider=result.provider,
                schema_version=result.schema_version,
                status=result.status.value,
                evidence_hash=bundle.evidence_hash if bundle is not None else None,
                observed_at=batch.observed_at,
                valid_until=(
                    bundle.valid_until
                    if bundle is not None
                    else batch.observed_at + timedelta(days=7)
                ),
                source_count=len(bundle.documents) if bundle is not None else 0,
                payload=serialize_issuer_bundle(bundle) if bundle is not None else None,
                error_code=result.error_code,
            )
            session.add(record)
            session.flush()
        records[result.identity.asset_id] = record
    return records


def _overlay_issuer_evidence(
    candidates: tuple[MarketCandidate, ...], batch: IssuerEvidenceBatch
) -> tuple[MarketCandidate, ...]:
    bundles = {
        (item.identity.asset_id, item.identity.isin): item.bundle
        for item in batch.results
        if item.bundle is not None
    }
    return tuple(
        replace(
            item,
            research=bundle.research,
            issuer_evidence=bundle,
        )
        if item.isin is not None
        and (bundle := bundles.get((item.asset_id, item.isin))) is not None
        else item
        for item in candidates
    )


def _materialize_admission(
    session: Session,
    *,
    snapshot: MarketResearchSnapshotRecord,
    candidates: tuple[MarketCandidate, ...],
    batch: IssuerEvidenceBatch,
    observed_at: datetime,
) -> tuple[AssetAdmissionRunRecord, dict[str, AssetAdmissionProfile]]:
    loaded = _load_admission(session, snapshot.id, batch.evidence_set_hash)
    if loaded is not None:
        run, profiles = loaded
        if run.expires_at < observed_at:
            raise MarketDataError(
                "ADMISSION_SNAPSHOT_EXPIRED",
                "asset-admission evidence expired; refresh issuer evidence before selection",
            )
        return loaded

    issuer_records = _persist_issuer_batch(session, batch)
    profiles = {
        item.asset_id: evaluate_asset_admission(item, calculated_at=observed_at)
        for item in candidates
    }
    status_counts = {
        status.value: sum(profile.overall_status is status for profile in profiles.values())
        for status in AdmissionStatus
    }
    expiry = min((profile.expires_at for profile in profiles.values()), default=observed_at)
    run = AssetAdmissionRunRecord(
        id=uuid4(),
        market_snapshot_id=snapshot.id,
        policy_version=ADMISSION_POLICY_VERSION,
        issuer_evidence_set_hash=batch.evidence_set_hash,
        scope="universe_discovery",
        status="succeeded",
        evaluated_at=observed_at,
        expires_at=expiry,
        assessment_count=len(profiles),
        status_counts=status_counts,
    )
    session.add(run)
    session.flush()
    session.add_all(
        AssetAdmissionAssessmentRecord(
            id=uuid4(),
            run_id=run.id,
            issuer_evidence_snapshot_id=(
                issuer_records[item.asset_id].id if item.asset_id in issuer_records else None
            ),
            asset_id=item.asset_id,
            name=item.name,
            instrument_kind=item.kind.value,
            strategy_profile=profiles[item.asset_id].strategy_profile,
            policy_version=ADMISSION_POLICY_VERSION,
            overall_status=profiles[item.asset_id].overall_status.value,
            evaluated_at=profiles[item.asset_id].evaluated_at,
            expires_at=profiles[item.asset_id].expires_at,
            profile=serialize_admission_profile(profiles[item.asset_id]),
        )
        for item in candidates
    )
    session.flush()
    return run, profiles


def acquire_market_research(
    session: Session,
    provider: MarketDataProvider,
    *,
    observed_at: datetime,
    cache_seconds: int,
    issuer_evidence_provider: IssuerEvidenceProvider | None = None,
    force: bool = False,
    idempotency_key: str | None = None,
) -> AcquiredMarketResearch:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise InvalidAllocationInput(
            "INVALID_MARKET_RESEARCH_TIME", "market research time must be timezone-aware"
        )
    if cache_seconds <= 0:
        raise InvalidAllocationInput(
            "INVALID_MARKET_RESEARCH_CACHE", "market research cache must be positive"
        )
    existing: MarketResearchSnapshotRecord | None = None
    expected_scan_policy = getattr(provider, "scan_policy_version", None)
    with session.begin():
        if idempotency_key is not None:
            existing = session.scalar(
                select(MarketResearchSnapshotRecord).where(
                    MarketResearchSnapshotRecord.idempotency_key == idempotency_key
                )
            )
        if existing is None and not force:
            query = select(MarketResearchSnapshotRecord).where(
                MarketResearchSnapshotRecord.status == "succeeded",
                MarketResearchSnapshotRecord.expires_at >= observed_at,
                MarketResearchSnapshotRecord.provider == provider.name,
            )
            if expected_scan_policy is not None:
                query = query.where(
                    MarketResearchSnapshotRecord.scan_policy_version == str(expected_scan_policy)
                )
            existing = session.scalar(
                query.order_by(MarketResearchSnapshotRecord.observed_at.desc()).limit(1)
            )
    if existing is not None:
        if existing.status != "succeeded":
            raise MarketDataError(
                existing.error_code or "MARKET_RESEARCH_FAILED",
                existing.error_detail or "market research snapshot failed",
            )
        record = existing
        base_candidates = tuple(deserialize_candidate(item) for item in existing.candidates)
        mode: Literal["live", "cached"] = "cached"
    else:
        key = idempotency_key or f"live:{uuid4()}"
        try:
            scan = _scan(provider, observed_at=observed_at)
        except MarketDataError as error:
            failed = MarketResearchSnapshotRecord(
                id=uuid4(),
                idempotency_key=key,
                scan_policy_version="unavailable",
                provider=provider.name,
                status="provider_error",
                error_code=error.code,
                error_detail=error.detail[:2000],
                observed_at=observed_at,
                expires_at=observed_at,
                universe_size=0,
                candidate_count=0,
                enriched_count=0,
                kind_counts={},
                candidates=[],
            )
            with session.begin():
                session.add(failed)
                session.flush()
            raise
        base_candidates = scan.candidates
        record = MarketResearchSnapshotRecord(
            id=uuid4(),
            idempotency_key=key,
            scan_policy_version=scan.policy_version,
            provider=provider.name,
            status="succeeded",
            error_code=None,
            error_detail=None,
            observed_at=scan.observed_at,
            expires_at=observed_at + timedelta(seconds=cache_seconds),
            universe_size=scan.universe_size,
            candidate_count=len(scan.candidates),
            enriched_count=scan.enriched_count,
            kind_counts=scan.kind_counts,
            candidates=[serialize_candidate(item) for item in scan.candidates],
        )
        with session.begin():
            session.add(record)
            session.flush()
        mode = "live"

    issuer_provider = issuer_evidence_provider or ReviewedIssuerCorpusProvider()
    batch = _acquire_issuer_batch(base_candidates, issuer_provider, observed_at=observed_at)
    candidates = _overlay_issuer_evidence(base_candidates, batch)
    with session.begin():
        admission_run, profiles = _materialize_admission(
            session,
            snapshot=record,
            candidates=candidates,
            batch=batch,
            observed_at=observed_at,
        )
    return AcquiredMarketResearch(record, candidates, mode, admission_run, profiles)


def latest_market_research(session: Session) -> MarketResearchSnapshotRecord | None:
    return session.scalar(
        select(MarketResearchSnapshotRecord)
        .order_by(MarketResearchSnapshotRecord.observed_at.desc())
        .limit(1)
    )


def latest_asset_admission(
    session: Session,
) -> tuple[AssetAdmissionRunRecord, list[AssetAdmissionAssessmentRecord]] | None:
    run = session.scalar(
        select(AssetAdmissionRunRecord)
        .order_by(AssetAdmissionRunRecord.evaluated_at.desc())
        .limit(1)
    )
    if run is None:
        return None
    assessments = list(
        session.scalars(
            select(AssetAdmissionAssessmentRecord)
            .where(AssetAdmissionAssessmentRecord.run_id == run.id)
            .order_by(
                AssetAdmissionAssessmentRecord.overall_status,
                AssetAdmissionAssessmentRecord.asset_id,
            )
        ).all()
    )
    return run, assessments


__all__ = [
    "AcquiredMarketResearch",
    "acquire_market_research",
    "deserialize_admission_profile",
    "deserialize_candidate",
    "latest_asset_admission",
    "latest_market_research",
    "serialize_admission_profile",
    "serialize_candidate",
]
