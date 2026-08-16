"""Strict issuer-evidence acquisition; unsupported coverage remains explicit."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.research.corpus import REVIEWED_ISSUER_EVIDENCE
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendIssuerEvidenceBundle,
    DividendResearchEvidence,
    IssuerAuditStatus,
    IssuerDecisionAuthority,
    IssuerEventEvidence,
    IssuerEventKind,
    IssuerEvidenceConflict,
    IssuerEvidenceStatus,
    IssuerGovernanceStatus,
    IssuerSourceDocument,
    IssuerSourceRole,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)


@dataclass(frozen=True, slots=True)
class IssuerIdentity:
    asset_id: str
    isin: str

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.isin.strip():
            raise InvalidAllocationInput(
                "INVALID_ISSUER_IDENTITY", "issuer asset id and ISIN are required"
            )


@dataclass(frozen=True, slots=True)
class IssuerEvidenceResult:
    identity: IssuerIdentity
    status: IssuerEvidenceStatus
    provider: str
    schema_version: str
    bundle: DividendIssuerEvidenceBundle | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status is IssuerEvidenceStatus.SUCCEEDED:
            if self.bundle is None or (
                self.bundle.asset_id != self.identity.asset_id
                or self.bundle.isin != self.identity.isin
            ):
                raise InvalidAllocationInput(
                    "INVALID_ISSUER_EVIDENCE_RESULT",
                    "successful issuer evidence must match the requested identity",
                )
        elif self.bundle is not None:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE_RESULT",
                "non-successful issuer evidence cannot contain a bundle",
            )


def issuer_evidence_set_hash(results: tuple[IssuerEvidenceResult, ...]) -> str:
    payload = sorted(
        (
            item.identity.asset_id,
            item.identity.isin,
            item.status.value,
            item.provider,
            item.schema_version,
            item.bundle.evidence_hash if item.bundle is not None else None,
            item.error_code,
        )
        for item in results
    )
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class IssuerEvidenceBatch:
    provider: str
    schema_version: str
    observed_at: datetime
    results: tuple[IssuerEvidenceResult, ...]

    @property
    def evidence_set_hash(self) -> str:
        return issuer_evidence_set_hash(self.results)


class IssuerEvidenceProvider(Protocol):
    name: str
    schema_version: str

    def acquire(
        self, *, identities: tuple[IssuerIdentity, ...], observed_at: datetime
    ) -> IssuerEvidenceBatch: ...


class ReviewedIssuerCorpusProvider:
    """Serve only reviewed, content-hashed official packets with exact identity matching."""

    name = "reviewed-official-corpus-v1"
    schema_version = "issuer-evidence-v2"

    def __init__(
        self, corpus: tuple[DividendIssuerEvidenceBundle, ...] = REVIEWED_ISSUER_EVIDENCE
    ) -> None:
        self._by_identity = {(item.asset_id, item.isin): item for item in corpus}
        self._by_asset = {item.asset_id: item for item in corpus}

    def acquire(
        self, *, identities: tuple[IssuerIdentity, ...], observed_at: datetime
    ) -> IssuerEvidenceBatch:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE_TIME", "issuer evidence time must be timezone-aware"
            )
        if len({(item.asset_id, item.isin) for item in identities}) != len(identities):
            raise InvalidAllocationInput(
                "DUPLICATE_ISSUER_IDENTITY", "issuer evidence identities must be unique"
            )
        results: list[IssuerEvidenceResult] = []
        for identity in identities:
            bundle = self._by_identity.get((identity.asset_id, identity.isin))
            if bundle is not None and bundle.observed_at <= observed_at:
                results.append(
                    IssuerEvidenceResult(
                        identity=identity,
                        status=IssuerEvidenceStatus.SUCCEEDED,
                        provider=self.name,
                        schema_version=self.schema_version,
                        bundle=bundle,
                    )
                )
            elif bundle is not None:
                results.append(
                    IssuerEvidenceResult(
                        identity=identity,
                        status=IssuerEvidenceStatus.UNAVAILABLE,
                        provider=self.name,
                        schema_version=self.schema_version,
                        error_code="ISSUER_EVIDENCE_NOT_YET_OBSERVED",
                    )
                )
            elif identity.asset_id in self._by_asset:
                results.append(
                    IssuerEvidenceResult(
                        identity=identity,
                        status=IssuerEvidenceStatus.INVALID,
                        provider=self.name,
                        schema_version=self.schema_version,
                        error_code="ISSUER_IDENTITY_MISMATCH",
                    )
                )
            else:
                results.append(
                    IssuerEvidenceResult(
                        identity=identity,
                        status=IssuerEvidenceStatus.UNSUPPORTED,
                        provider=self.name,
                        schema_version=self.schema_version,
                        error_code="ISSUER_EVIDENCE_UNSUPPORTED",
                    )
                )
        return IssuerEvidenceBatch(
            provider=self.name,
            schema_version=self.schema_version,
            observed_at=observed_at,
            results=tuple(results),
        )


def serialize_issuer_bundle(bundle: DividendIssuerEvidenceBundle) -> dict[str, object]:
    research = bundle.research
    return {
        "schema_version": bundle.schema_version,
        "policy_version": bundle.policy_version,
        "provider": bundle.provider,
        "asset_id": bundle.asset_id,
        "isin": bundle.isin,
        "observed_at": bundle.observed_at.isoformat(),
        "valid_until": bundle.valid_until.isoformat(),
        "latest_period_profitable": bundle.latest_period_profitable,
        "audit_status": bundle.audit_status.value,
        "positive_equity": bundle.positive_equity,
        "governance_status": bundle.governance_status.value,
        "event_coverage_through": bundle.event_coverage_through.isoformat(),
        "research": {
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
        },
        "documents": [
            {
                "source_id": item.source_id,
                "role": item.role.value,
                "title": item.title,
                "url": item.url,
                "publisher": item.publisher,
                "asset_id": item.asset_id,
                "isin": item.isin,
                "published_at": item.published_at.isoformat(),
                "retrieved_at": item.retrieved_at.isoformat(),
                "fact_effective_at": item.fact_effective_at.isoformat(),
                "content_sha256": item.content_sha256,
            }
            for item in bundle.documents
        ],
        "events": [
            {
                "event_id": item.event_id,
                "kind": item.kind.value,
                "authority": item.authority.value,
                "source_id": item.source_id,
                "effective_from": item.effective_from.isoformat(),
                "effective_until": (
                    item.effective_until.isoformat() if item.effective_until is not None else None
                ),
                "summary": item.summary,
            }
            for item in bundle.events
        ],
        "conflicts": [
            {
                "conflict_id": item.conflict_id,
                "fact_kind": item.fact_kind,
                "source_ids": list(item.source_ids),
            }
            for item in bundle.conflicts
        ],
        "evidence_hash": bundle.evidence_hash,
    }


def _optional_date(value: object | None) -> date | None:
    return date.fromisoformat(str(value)) if value is not None else None


def _optional_decimal(value: object | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def deserialize_issuer_bundle(payload: dict[str, object]) -> DividendIssuerEvidenceBundle:
    raw_research = cast(dict[str, object], payload["research"])
    research = DividendResearchEvidence(
        schema_version=str(raw_research["schema_version"]),
        policy_version=str(raw_research["policy_version"]),
        scope=ResearchScope(str(raw_research["scope"])),
        observed_at=datetime.fromisoformat(str(raw_research["observed_at"])),
        max_age=timedelta(seconds=int(cast(int, raw_research["max_age_seconds"]))),
        reporting_period_end=_optional_date(raw_research.get("reporting_period_end")),
        profitable_years=cast(int | None, raw_research.get("profitable_years")),
        dividend_years=int(cast(int, raw_research["dividend_years"])),
        payout_ratio_percent=_optional_decimal(raw_research.get("payout_ratio_percent")),
        balance_sheet_status=BalanceSheetStatus(str(raw_research["balance_sheet_status"])),
        governance_program_member=cast(
            bool | None, raw_research.get("governance_program_member")
        ),
        corporate_action_status=CorporateActionStatus(
            str(raw_research["corporate_action_status"])
        ),
        summary=str(raw_research["summary"]),
        citations=tuple(
            ResearchCitation(
                kind=ResearchFactKind(str(item["kind"])),
                title=str(item["title"]),
                url=str(item["url"]),
            )
            for item in cast(list[dict[str, object]], raw_research["citations"])
        ),
        annual_dividend_per_share=_optional_decimal(
            raw_research.get("annual_dividend_per_share")
        ),
        historical_dividend_yield_percent=_optional_decimal(
            raw_research.get("historical_dividend_yield_percent")
        ),
        last_registry_close_date=_optional_date(raw_research.get("last_registry_close_date")),
        listing_level=cast(int | None, raw_research.get("listing_level")),
        unknown_facts=tuple(cast(list[str], raw_research.get("unknown_facts", []))),
    )
    documents = tuple(
        IssuerSourceDocument(
            source_id=str(item["source_id"]),
            role=IssuerSourceRole(str(item["role"])),
            title=str(item["title"]),
            url=str(item["url"]),
            publisher=str(item["publisher"]),
            asset_id=str(item["asset_id"]),
            isin=str(item["isin"]),
            published_at=datetime.fromisoformat(str(item["published_at"])),
            retrieved_at=datetime.fromisoformat(str(item["retrieved_at"])),
            fact_effective_at=date.fromisoformat(str(item["fact_effective_at"])),
            content_sha256=str(item["content_sha256"]),
        )
        for item in cast(list[dict[str, object]], payload["documents"])
    )
    events = tuple(
        IssuerEventEvidence(
            event_id=str(item["event_id"]),
            kind=IssuerEventKind(str(item["kind"])),
            authority=IssuerDecisionAuthority(str(item["authority"])),
            source_id=str(item["source_id"]),
            effective_from=date.fromisoformat(str(item["effective_from"])),
            effective_until=_optional_date(item.get("effective_until")),
            summary=str(item.get("summary", "")),
        )
        for item in cast(list[dict[str, object]], payload.get("events", []))
    )
    conflicts = tuple(
        IssuerEvidenceConflict(
            conflict_id=str(item["conflict_id"]),
            fact_kind=str(item["fact_kind"]),
            source_ids=tuple(cast(list[str], item["source_ids"])),
        )
        for item in cast(list[dict[str, object]], payload.get("conflicts", []))
    )
    bundle = DividendIssuerEvidenceBundle(
        schema_version=str(payload["schema_version"]),
        policy_version=str(payload["policy_version"]),
        provider=str(payload["provider"]),
        asset_id=str(payload["asset_id"]),
        isin=str(payload["isin"]),
        observed_at=datetime.fromisoformat(str(payload["observed_at"])),
        valid_until=datetime.fromisoformat(str(payload["valid_until"])),
        research=research,
        audit_status=IssuerAuditStatus(str(payload["audit_status"])),
        latest_period_profitable=cast(bool | None, payload.get("latest_period_profitable")),
        positive_equity=cast(bool | None, payload.get("positive_equity")),
        governance_status=IssuerGovernanceStatus(str(payload["governance_status"])),
        event_coverage_through=datetime.fromisoformat(str(payload["event_coverage_through"])),
        documents=documents,
        events=events,
        conflicts=conflicts,
    )
    expected_hash = payload.get("evidence_hash")
    if expected_hash is not None and str(expected_hash) != bundle.evidence_hash:
        raise InvalidAllocationInput(
            "ISSUER_EVIDENCE_HASH_MISMATCH",
            "persisted issuer evidence does not match its immutable content hash",
        )
    return bundle


__all__ = [
    "IssuerEvidenceBatch",
    "IssuerEvidenceProvider",
    "IssuerEvidenceResult",
    "IssuerIdentity",
    "ReviewedIssuerCorpusProvider",
    "deserialize_issuer_bundle",
    "issuer_evidence_set_hash",
    "serialize_issuer_bundle",
]
