"""Acquire immutable market snapshots from a bounded source-backed scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import (
    InstrumentKind,
    MarketCandidate,
    MarketDataProvider,
    MarketScan,
    MarketScanProvider,
)
from patientcapital.persistence.models import MarketResearchSnapshotRecord
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)


@dataclass(frozen=True, slots=True)
class AcquiredMarketResearch:
    record: MarketResearchSnapshotRecord
    candidates: tuple[MarketCandidate, ...]
    mode: Literal["live", "cached"]


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


def deserialize_candidate(payload: dict[str, object]) -> MarketCandidate:
    research_payload = payload.get("research")
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


def acquire_market_research(
    session: Session,
    provider: MarketDataProvider,
    *,
    observed_at: datetime,
    cache_seconds: int,
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
    with session.begin():
        if idempotency_key is not None:
            existing = session.scalar(
                select(MarketResearchSnapshotRecord).where(
                    MarketResearchSnapshotRecord.idempotency_key == idempotency_key
                )
            )
        if existing is None and not force:
            existing = session.scalar(
                select(MarketResearchSnapshotRecord)
                .where(
                    MarketResearchSnapshotRecord.status == "succeeded",
                    MarketResearchSnapshotRecord.expires_at >= observed_at,
                )
                .order_by(MarketResearchSnapshotRecord.observed_at.desc())
                .limit(1)
            )
    if existing is not None:
        if existing.status != "succeeded":
            raise MarketDataError(
                existing.error_code or "MARKET_RESEARCH_FAILED",
                existing.error_detail or "market research snapshot failed",
            )
        return AcquiredMarketResearch(
            existing,
            tuple(deserialize_candidate(item) for item in existing.candidates),
            "cached",
        )

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
    serialized = [serialize_candidate(item) for item in scan.candidates]
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
        candidates=serialized,
    )
    with session.begin():
        session.add(record)
        session.flush()
    return AcquiredMarketResearch(record, scan.candidates, "live")


def latest_market_research(session: Session) -> MarketResearchSnapshotRecord | None:
    return session.scalar(
        select(MarketResearchSnapshotRecord)
        .order_by(MarketResearchSnapshotRecord.observed_at.desc())
        .limit(1)
    )


__all__ = [
    "AcquiredMarketResearch",
    "acquire_market_research",
    "deserialize_candidate",
    "latest_market_research",
    "serialize_candidate",
]
