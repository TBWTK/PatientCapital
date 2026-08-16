"""Immutable research evidence; narrative never owns allocation facts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlparse

from patientcapital.domain.errors import InvalidAllocationInput

_PRIMARY_SOURCE_HOSTS = frozenset(
    {
        "cbr.ru",
        "fs.moex.com",
        "iss.moex.com",
        "moex.com",
        "www.cbr.ru",
        "www.moex.com",
    }
)


class ResearchFactKind(StrEnum):
    LISTING = "listing"
    FUNDAMENTALS = "fundamentals"
    DIVIDENDS = "dividends"
    GOVERNANCE = "governance"
    CORPORATE_ACTIONS = "corporate_actions"


class BalanceSheetStatus(StrEnum):
    NO_DEBT = "no_debt"
    ADEQUATE_CAPITAL = "adequate_capital"
    CONCERN = "concern"
    UNKNOWN = "unknown"


class CorporateActionStatus(StrEnum):
    NO_MATERIAL_ACTION_IDENTIFIED = "no_material_action_identified"
    MATERIAL = "material"
    UNKNOWN = "unknown"


class ResearchScope(StrEnum):
    FULL_QUALITY = "full_quality"
    MARKET_SCREEN = "market_screen"


class IssuerEvidenceStatus(StrEnum):
    SUCCEEDED = "succeeded"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class IssuerSourceRole(StrEnum):
    IDENTITY = "identity"
    FINANCIALS = "financials"
    AUDIT = "audit"
    DIVIDENDS = "dividends"
    GOVERNANCE = "governance"
    CORPORATE_ACTIONS = "corporate_actions"


class IssuerDecisionAuthority(StrEnum):
    BINDING = "binding"
    NON_BINDING = "non_binding"
    HISTORICAL_FACT = "historical_fact"


class IssuerEventKind(StrEnum):
    DIVIDEND_DECLARED = "dividend_declared"
    DIVIDEND_PAID = "dividend_paid"
    DIVIDEND_SUSPENDED = "dividend_suspended"
    DIVIDEND_RESUMED = "dividend_resumed"
    DIVIDEND_CANCELLED = "dividend_cancelled"
    DEFAULT_OR_INSOLVENCY = "default_or_insolvency"
    DELISTING = "delisting"
    DILUTION = "dilution"
    RELATED_PARTY = "related_party"
    GOVERNANCE_CHANGE = "governance_change"
    RESTRUCTURING = "restructuring"


class IssuerAuditStatus(StrEnum):
    CLEAN = "clean"
    QUALIFIED = "qualified"
    GOING_CONCERN = "going_concern"
    ADVERSE = "adverse"
    UNKNOWN = "unknown"


class IssuerGovernanceStatus(StrEnum):
    CLEAR = "clear"
    REVIEW = "review"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResearchCitation:
    kind: ResearchFactKind
    title: str
    url: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.hostname.lower() not in _PRIMARY_SOURCE_HOSTS
        ):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE",
                "research citations must use an allowlisted primary HTTPS source",
            )
        if not self.title.strip():
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research citation title is required"
            )


@dataclass(frozen=True, slots=True)
class DividendResearchEvidence:
    schema_version: str
    policy_version: str
    observed_at: datetime
    max_age: timedelta
    reporting_period_end: date | None
    profitable_years: int | None
    dividend_years: int
    payout_ratio_percent: Decimal | None
    balance_sheet_status: BalanceSheetStatus
    governance_program_member: bool | None
    corporate_action_status: CorporateActionStatus
    summary: str
    citations: tuple[ResearchCitation, ...]
    scope: ResearchScope = ResearchScope.FULL_QUALITY
    annual_dividend_per_share: Decimal | None = None
    historical_dividend_yield_percent: Decimal | None = None
    last_registry_close_date: date | None = None
    listing_level: int | None = None
    unknown_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_version.strip() or not self.policy_version.strip():
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research schema and policy versions are required"
            )
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research observed_at must be timezone-aware"
            )
        if self.max_age <= timedelta(0):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research max_age must be positive"
            )
        if (
            self.reporting_period_end is not None
            and self.reporting_period_end > self.observed_at.date()
        ):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research reporting period cannot be in the future"
            )
        year_counts = (
            ("profitable_years", self.profitable_years),
            ("dividend_years", self.dividend_years),
        )
        for name, value in year_counts:
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise InvalidAllocationInput(
                    "INVALID_RESEARCH_EVIDENCE", f"{name} must be a non-negative integer"
                )
        if self.payout_ratio_percent is not None and (
            not isinstance(self.payout_ratio_percent, Decimal)
            or not self.payout_ratio_percent.is_finite()
            or self.payout_ratio_percent < 0
        ):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "payout ratio must be a non-negative finite Decimal"
            )
        if self.governance_program_member is not None and not isinstance(
            self.governance_program_member, bool
        ):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "governance status must be boolean"
            )
        if not self.summary.strip():
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research summary is required"
            )
        kinds = [citation.kind for citation in self.citations]
        if self.scope is ResearchScope.FULL_QUALITY:
            required = {
                ResearchFactKind.FUNDAMENTALS,
                ResearchFactKind.DIVIDENDS,
                ResearchFactKind.GOVERNANCE,
                ResearchFactKind.CORPORATE_ACTIONS,
            }
            if (
                self.reporting_period_end is None
                or self.profitable_years is None
                or self.payout_ratio_percent is None
                or self.governance_program_member is None
            ):
                raise InvalidAllocationInput(
                    "INVALID_RESEARCH_EVIDENCE",
                    "full-quality research requires every material gate",
                )
        else:
            required = {ResearchFactKind.LISTING, ResearchFactKind.DIVIDENDS}
            required_unknowns = {
                "profitability",
                "payout",
                "balance",
                "governance",
                "corporate_actions",
            }
            numeric = (
                self.annual_dividend_per_share,
                self.historical_dividend_yield_percent,
            )
            if (
                self.policy_version != "dividend-market-screen-v1"
                or self.listing_level not in {1, 2}
                or any(
                    value is None
                    or not isinstance(value, Decimal)
                    or not value.is_finite()
                    or value < 0
                    for value in numeric
                )
                or set(self.unknown_facts) != required_unknowns
            ):
                raise InvalidAllocationInput(
                    "INVALID_RESEARCH_EVIDENCE",
                    "market-screen research requires listing, dividend metrics "
                    "and explicit unknowns",
                )
        if set(kinds) != required or len(kinds) != len(required):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE",
                "research requires one primary citation for every gate category",
            )

    def is_fresh_at(self, calculated_at: datetime) -> bool:
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            return False
        age = calculated_at - self.observed_at
        return timedelta(0) <= age <= self.max_age


@dataclass(frozen=True, slots=True)
class IssuerSourceDocument:
    source_id: str
    role: IssuerSourceRole
    title: str
    url: str
    publisher: str
    asset_id: str
    isin: str
    published_at: datetime
    retrieved_at: datetime
    fact_effective_at: date
    content_sha256: str

    def __post_init__(self) -> None:
        values = (self.source_id, self.title, self.publisher, self.asset_id, self.isin)
        if any(not value.strip() for value in values):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer source identity fields are required"
            )
        parsed = urlparse(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.hostname.lower() not in _PRIMARY_SOURCE_HOSTS
        ):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE",
                "issuer source must use an allowlisted primary HTTPS host",
            )
        for name, value in (
            ("published_at", self.published_at),
            ("retrieved_at", self.retrieved_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise InvalidAllocationInput(
                    "INVALID_ISSUER_EVIDENCE", f"issuer source {name} must be timezone-aware"
                )
        if self.published_at > self.retrieved_at:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer source cannot be retrieved before publication"
            )
        if self.fact_effective_at > self.retrieved_at.date():
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer fact cannot be effective in the future"
            )
        if re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer source content hash must be SHA-256"
            )


@dataclass(frozen=True, slots=True)
class IssuerEventEvidence:
    event_id: str
    kind: IssuerEventKind
    authority: IssuerDecisionAuthority
    source_id: str
    effective_from: date
    effective_until: date | None = None
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.source_id.strip():
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer event identity is required"
            )
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer event interval is invalid"
            )


@dataclass(frozen=True, slots=True)
class IssuerEvidenceConflict:
    conflict_id: str
    fact_kind: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.conflict_id.strip()
            or not self.fact_kind.strip()
            or len(self.source_ids) < 2
            or len(set(self.source_ids)) != len(self.source_ids)
        ):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer evidence conflict is invalid"
            )


@dataclass(frozen=True, slots=True)
class DividendIssuerEvidenceBundle:
    schema_version: str
    policy_version: str
    provider: str
    asset_id: str
    isin: str
    observed_at: datetime
    valid_until: datetime
    research: DividendResearchEvidence
    audit_status: IssuerAuditStatus
    latest_period_profitable: bool | None
    positive_equity: bool | None
    governance_status: IssuerGovernanceStatus
    event_coverage_through: datetime
    documents: tuple[IssuerSourceDocument, ...]
    events: tuple[IssuerEventEvidence, ...] = ()
    conflicts: tuple[IssuerEvidenceConflict, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "issuer-evidence-v2":
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer evidence schema version is unsupported"
            )
        if self.policy_version != "equity-dividend-quality-v2":
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer evidence policy version is unsupported"
            )
        if not self.provider.strip() or not self.asset_id.strip() or not self.isin.strip():
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer evidence identity is required"
            )
        for name, value in (
            ("observed_at", self.observed_at),
            ("valid_until", self.valid_until),
            ("event_coverage_through", self.event_coverage_through),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise InvalidAllocationInput(
                    "INVALID_ISSUER_EVIDENCE", f"issuer evidence {name} must be timezone-aware"
                )
        if self.valid_until <= self.observed_at:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer evidence validity interval is invalid"
            )
        if self.event_coverage_through > self.observed_at:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "event coverage cannot exceed observation time"
            )
        if self.research.observed_at > self.observed_at:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE",
                "issuer research cannot be observed after its evidence bundle",
            )
        if self.research.scope is not ResearchScope.FULL_QUALITY:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer bundle requires full-quality research"
            )
        if self.research.policy_version != self.policy_version:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer bundle and research policy must match"
            )
        source_ids = [item.source_id for item in self.documents]
        if not source_ids or len(source_ids) != len(set(source_ids)):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer source ids must be present and unique"
            )
        if any(
            item.asset_id != self.asset_id or item.isin != self.isin for item in self.documents
        ):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer source identity does not match the bundle"
            )
        if any(item.retrieved_at > self.observed_at for item in self.documents):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE",
                "issuer documents cannot be retrieved after the bundle observation",
            )
        source_id_set = set(source_ids)
        if any(item.source_id not in source_id_set for item in self.events):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer event references an unknown source"
            )
        if any(not set(item.source_ids) <= source_id_set for item in self.conflicts):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer conflict references an unknown source"
            )
        event_ids = [item.event_id for item in self.events]
        conflict_ids = [item.conflict_id for item in self.conflicts]
        if len(event_ids) != len(set(event_ids)) or len(conflict_ids) != len(set(conflict_ids)):
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer event/conflict ids must be unique"
            )
        required_roles = {
            IssuerSourceRole.IDENTITY,
            IssuerSourceRole.FINANCIALS,
            IssuerSourceRole.AUDIT,
            IssuerSourceRole.DIVIDENDS,
            IssuerSourceRole.GOVERNANCE,
            IssuerSourceRole.CORPORATE_ACTIONS,
        }
        if not required_roles <= {item.role for item in self.documents}:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "issuer bundle lacks a required primary-source role"
            )
        citation_urls = {item.url for item in self.research.citations}
        if not citation_urls <= {item.url for item in self.documents}:
            raise InvalidAllocationInput(
                "INVALID_ISSUER_EVIDENCE", "research citations must belong to issuer documents"
            )

    def is_fresh_at(self, calculated_at: datetime) -> bool:
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            return False
        return self.observed_at <= calculated_at <= self.valid_until

    @property
    def evidence_hash(self) -> str:
        research = self.research
        payload = {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "provider": self.provider,
            "asset_id": self.asset_id,
            "isin": self.isin,
            "observed_at": self.observed_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "research": {
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
                "corporate_action_status": research.corporate_action_status.value,
                "last_registry_close_date": (
                    research.last_registry_close_date.isoformat()
                    if research.last_registry_close_date is not None
                    else None
                ),
            },
            "audit_status": self.audit_status.value,
            "latest_period_profitable": self.latest_period_profitable,
            "positive_equity": self.positive_equity,
            "governance_status": self.governance_status.value,
            "event_coverage_through": self.event_coverage_through.isoformat(),
            "documents": sorted(
                (
                    item.source_id,
                    item.role.value,
                    item.url,
                    item.asset_id,
                    item.isin,
                    item.published_at.isoformat(),
                    item.retrieved_at.isoformat(),
                    item.fact_effective_at.isoformat(),
                    item.content_sha256,
                )
                for item in self.documents
            ),
            "events": sorted(
                (
                    item.event_id,
                    item.kind.value,
                    item.authority.value,
                    item.source_id,
                    item.effective_from.isoformat(),
                    item.effective_until.isoformat() if item.effective_until is not None else None,
                )
                for item in self.events
            ),
            "conflicts": sorted(
                (item.conflict_id, item.fact_kind, sorted(item.source_ids))
                for item in self.conflicts
            ),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
