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
