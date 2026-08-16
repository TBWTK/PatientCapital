"""Immutable research evidence; narrative never owns allocation facts."""

from __future__ import annotations

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
    reporting_period_end: date
    profitable_years: int
    dividend_years: int
    payout_ratio_percent: Decimal
    balance_sheet_status: BalanceSheetStatus
    governance_program_member: bool
    corporate_action_status: CorporateActionStatus
    summary: str
    citations: tuple[ResearchCitation, ...]

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
        if self.reporting_period_end > self.observed_at.date():
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research reporting period cannot be in the future"
            )
        for name, value in (
            ("profitable_years", self.profitable_years),
            ("dividend_years", self.dividend_years),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidAllocationInput(
                    "INVALID_RESEARCH_EVIDENCE", f"{name} must be a non-negative integer"
                )
        if (
            not isinstance(self.payout_ratio_percent, Decimal)
            or not self.payout_ratio_percent.is_finite()
            or self.payout_ratio_percent < 0
        ):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "payout ratio must be a non-negative finite Decimal"
            )
        if not isinstance(self.governance_program_member, bool):
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "governance status must be boolean"
            )
        if not self.summary.strip():
            raise InvalidAllocationInput(
                "INVALID_RESEARCH_EVIDENCE", "research summary is required"
            )
        kinds = [citation.kind for citation in self.citations]
        required = set(ResearchFactKind)
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
