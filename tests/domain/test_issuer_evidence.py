from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.admission import AdmissionStatus, evaluate_asset_admission
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketLiquidityEvidence,
)
from patientcapital.research.corpus import MOEX_ISSUER_EVIDENCE_V2
from patientcapital.research.models import (
    IssuerAuditStatus,
    IssuerDecisionAuthority,
    IssuerEventEvidence,
    IssuerEventKind,
    IssuerEvidenceConflict,
    IssuerEvidenceStatus,
)
from patientcapital.research.provider import (
    IssuerIdentity,
    ReviewedIssuerCorpusProvider,
    deserialize_issuer_bundle,
    issuer_evidence_set_hash,
    serialize_issuer_bundle,
)

NOW = datetime(2026, 8, 16, 15, 30, tzinfo=UTC)


def _liquidity() -> MarketLiquidityEvidence:
    observations = tuple(
        LiquidityObservation(
            session_date=date(2026, 7, 20) + timedelta(days=index),
            turnover_rub=Decimal("100000000"),
            trades=100,
            bid=Decimal("100"),
            offer=Decimal("100.10"),
        )
        for index in range(20)
    )
    return MarketLiquidityEvidence(
        policy_version="market-liquidity-v2",
        observed_at=NOW,
        max_age=timedelta(days=4),
        security_status="active",
        source_url="https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR",
        observations=observations,
    )


def _candidate(evidence=MOEX_ISSUER_EVIDENCE_V2) -> MarketCandidate:  # type: ignore[no-untyped-def]
    return MarketCandidate(
        asset_id="MOEX",
        isin="RU000A0JR4A1",
        name="Moscow Exchange",
        kind=InstrumentKind.PUBLIC_EQUITY,
        currency="RUB",
        lot_size=10,
        unit_price=Decimal("180"),
        price_as_of=NOW,
        max_age=timedelta(days=4),
        source_url="https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR",
        classification_url="https://www.moex.com/ru/listing/securities-list.aspx",
        quote_kind="LAST",
        turnover=Decimal("100000000"),
        research=evidence.research if evidence is not None else None,
        issuer_evidence=evidence,
        liquidity=_liquidity(),
    )


def test_evidence_hash_is_order_and_narrative_invariant() -> None:
    reordered = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        research=replace(MOEX_ISSUER_EVIDENCE_V2.research, summary="Hostile prose."),
        documents=tuple(reversed(MOEX_ISSUER_EVIDENCE_V2.documents)),
        events=tuple(reversed(MOEX_ISSUER_EVIDENCE_V2.events)),
    )

    assert reordered.evidence_hash == MOEX_ISSUER_EVIDENCE_V2.evidence_hash


def test_source_content_hash_changes_evidence_identity() -> None:
    changed_document = replace(
        MOEX_ISSUER_EVIDENCE_V2.documents[0],
        content_sha256="f" * 64,
    )
    changed = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        documents=(changed_document, *MOEX_ISSUER_EVIDENCE_V2.documents[1:]),
    )

    assert changed.evidence_hash != MOEX_ISSUER_EVIDENCE_V2.evidence_hash


def test_untrusted_or_future_source_is_rejected_at_boundary() -> None:
    source = MOEX_ISSUER_EVIDENCE_V2.documents[0]

    with pytest.raises(InvalidAllocationInput, match="allowlisted primary HTTPS host"):
        replace(source, url="https://example.com/opinion")

    with pytest.raises(InvalidAllocationInput, match="retrieved before publication"):
        replace(source, published_at=source.retrieved_at + timedelta(seconds=1))


def test_evidence_payload_round_trip_preserves_content_hash() -> None:
    restored = deserialize_issuer_bundle(serialize_issuer_bundle(MOEX_ISSUER_EVIDENCE_V2))

    assert restored == MOEX_ISSUER_EVIDENCE_V2
    assert restored.evidence_hash == MOEX_ISSUER_EVIDENCE_V2.evidence_hash


def test_reviewed_provider_requires_exact_security_identity() -> None:
    provider = ReviewedIssuerCorpusProvider()

    batch = provider.acquire(
        identities=(
            IssuerIdentity("MOEX", "RU000A0JR4A1"),
            IssuerIdentity("MOEX", "WRONG"),
            IssuerIdentity("SBER", "RU0009029540"),
        ),
        observed_at=NOW,
    )

    assert [item.status for item in batch.results] == [
        IssuerEvidenceStatus.SUCCEEDED,
        IssuerEvidenceStatus.INVALID,
        IssuerEvidenceStatus.UNSUPPORTED,
    ]
    assert batch.results[0].bundle is MOEX_ISSUER_EVIDENCE_V2
    assert issuer_evidence_set_hash(tuple(reversed(batch.results))) == batch.evidence_set_hash


def test_valid_reviewed_equity_packet_is_eligible() -> None:
    profile = evaluate_asset_admission(_candidate(), calculated_at=NOW)

    assert profile.investment.policy_version == "equity-dividend-quality-v2"
    assert profile.investment.status is AdmissionStatus.ELIGIBLE
    assert "EQDV2_ELIGIBLE" in profile.investment.reason_codes


def test_legacy_research_without_v2_bundle_fails_closed() -> None:
    profile = evaluate_asset_admission(_candidate(None), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.UNKNOWN
    assert "EQDV2_EVIDENCE_MISSING" in profile.unknowns


def test_binding_dividend_suspension_is_strategy_hard_kill() -> None:
    event = IssuerEventEvidence(
        event_id="moex-suspension",
        kind=IssuerEventKind.DIVIDEND_SUSPENDED,
        authority=IssuerDecisionAuthority.BINDING,
        source_id="moex-fy2025-agm-dividends",
        effective_from=NOW.date(),
    )
    evidence = replace(MOEX_ISSUER_EVIDENCE_V2, events=(*MOEX_ISSUER_EVIDENCE_V2.events, event))

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.REJECT
    assert "EQDV2_BINDING_DIVIDEND_SUSPENSION" in profile.hard_kills


def test_nonbinding_suspension_is_watch_not_reject() -> None:
    event = IssuerEventEvidence(
        event_id="moex-comment",
        kind=IssuerEventKind.DIVIDEND_SUSPENDED,
        authority=IssuerDecisionAuthority.NON_BINDING,
        source_id="moex-fy2025-agm-dividends",
        effective_from=NOW.date(),
    )
    evidence = replace(MOEX_ISSUER_EVIDENCE_V2, events=(*MOEX_ISSUER_EVIDENCE_V2.events, event))

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.WATCH
    assert not profile.hard_kills
    assert "EQDV2_DIVIDEND_NONBINDING_ADVERSE" in profile.investment.reason_codes


def test_going_concern_audit_is_hard_kill() -> None:
    evidence = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        audit_status=IssuerAuditStatus.GOING_CONCERN,
    )

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.REJECT
    assert "EQDV2_GOING_CONCERN" in profile.hard_kills


def test_negative_equity_is_rejected() -> None:
    evidence = replace(MOEX_ISSUER_EVIDENCE_V2, positive_equity=False)

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.REJECT
    assert "EQDV2_NEGATIVE_EQUITY" in profile.investment.reason_codes


def test_conflicting_primary_facts_are_unknown() -> None:
    source_ids = tuple(item.source_id for item in MOEX_ISSUER_EVIDENCE_V2.documents[:2])
    evidence = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        conflicts=(IssuerEvidenceConflict("profit-conflict", "profit", source_ids),),
    )

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.UNKNOWN
    assert "EQDV2_FACT_CONFLICT" in profile.unknowns


def test_event_coverage_older_than_eight_hours_is_unknown() -> None:
    evidence = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        event_coverage_through=NOW - timedelta(hours=9),
    )

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.UNKNOWN
    assert "EQDV2_EVENT_COVERAGE_STALE" in profile.unknowns


def test_old_reporting_period_stays_unknown_after_fresh_download() -> None:
    research = replace(
        MOEX_ISSUER_EVIDENCE_V2.research,
        observed_at=NOW,
        reporting_period_end=date(2025, 12, 31),
    )
    evidence = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        observed_at=NOW,
        valid_until=NOW + timedelta(days=180),
        event_coverage_through=NOW,
        research=research,
        documents=tuple(
            replace(item, retrieved_at=NOW) for item in MOEX_ISSUER_EVIDENCE_V2.documents
        ),
    )

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is AdmissionStatus.UNKNOWN
    assert "EQDV2_FINANCIALS_STALE_PERIOD" in profile.unknowns


@pytest.mark.parametrize(
    ("payout", "expected_status", "expected_reason"),
    [
        (Decimal("100"), AdmissionStatus.ELIGIBLE, "EQDV2_ELIGIBLE"),
        (Decimal("100.00000001"), AdmissionStatus.REJECT, "EQDV2_PAYOUT_UNCOVERED"),
    ],
)
def test_payout_decimal_boundary_is_exact(
    payout: Decimal,
    expected_status: AdmissionStatus,
    expected_reason: str,
) -> None:
    evidence = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        research=replace(MOEX_ISSUER_EVIDENCE_V2.research, payout_ratio_percent=payout),
    )

    profile = evaluate_asset_admission(_candidate(evidence), calculated_at=NOW)

    assert profile.investment.status is expected_status
    assert expected_reason in profile.investment.reason_codes
