"""Reviewed primary-source corpus admitted to the first dividend policy."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
)

MOEX_DIVIDEND_RESEARCH = DividendResearchEvidence(
    schema_version="dividend-research-evidence-v1",
    policy_version="dividend-quality-v1",
    observed_at=datetime(2026, 8, 16, 0, 0, tzinfo=UTC),
    max_age=timedelta(days=180),
    reporting_period_end=date(2025, 12, 31),
    profitable_years=4,
    dividend_years=4,
    payout_ratio_percent=Decimal("75.00"),
    balance_sheet_status=BalanceSheetStatus.NO_DEBT,
    governance_program_member=True,
    corporate_action_status=CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED,
    last_registry_close_date=date(2025, 7, 18),
    summary=(
        "MOEX показывает положительную прибыль за четыре года, дивиденды за четыре последних "
        "отчётных периода, выплату 75% прибыли за 2025 год и отсутствие долговых обязательств. "
        "Участие в программе акционерной стоимости покрывает отдельную governance-проверку."
    ),
    citations=(
        ResearchCitation(
            kind=ResearchFactKind.FUNDAMENTALS,
            title="МСФО-результаты MOEX за 2025 год",
            url="https://www.moex.com/n98156",
        ),
        ResearchCitation(
            kind=ResearchFactKind.DIVIDENDS,
            title="Дивиденды и дивидендная история MOEX",
            url="https://www.moex.com/a2656",
        ),
        ResearchCitation(
            kind=ResearchFactKind.GOVERNANCE,
            title="Программа создания акционерной стоимости MOEX и Банка России",
            url=(
                "https://www.moex.com/programma-sozdaniya-aktsionernoj-stoimosti-"
                "publichnyh-aktsionernyh-obschestv"
            ),
        ),
        ResearchCitation(
            kind=ResearchFactKind.CORPORATE_ACTIONS,
            title="Материалы годового собрания MOEX за 2025 год",
            url=("https://www.moex.com/povtornoe-godovoe-zasedanie-obschego-sobraniya-aktsionerov"),
        ),
    ),
)

__all__ = ["MOEX_DIVIDEND_RESEARCH"]
