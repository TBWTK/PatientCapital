"""Reviewed primary-source corpus admitted to the first dividend policy."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendIssuerEvidenceBundle,
    DividendResearchEvidence,
    IssuerAuditStatus,
    IssuerDecisionAuthority,
    IssuerEventEvidence,
    IssuerEventKind,
    IssuerGovernanceStatus,
    IssuerSourceDocument,
    IssuerSourceRole,
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

_MOEX_REVIEWED_AT = datetime(2026, 8, 16, 15, 0, tzinfo=UTC)
_MOEX_AGM_URL = "https://www.moex.com/n101427?nt=120"

MOEX_ISSUER_EVIDENCE_V2 = DividendIssuerEvidenceBundle(
    schema_version="issuer-evidence-v2",
    policy_version="equity-dividend-quality-v2",
    provider="reviewed-official-corpus-v1",
    asset_id="MOEX",
    isin="RU000A0JR4A1",
    observed_at=_MOEX_REVIEWED_AT,
    valid_until=_MOEX_REVIEWED_AT + timedelta(days=180),
    research=DividendResearchEvidence(
        schema_version="dividend-research-evidence-v2",
        policy_version="equity-dividend-quality-v2",
        observed_at=_MOEX_REVIEWED_AT,
        max_age=timedelta(days=180),
        reporting_period_end=date(2026, 3, 31),
        profitable_years=4,
        dividend_years=4,
        payout_ratio_percent=Decimal("75.00"),
        balance_sheet_status=BalanceSheetStatus.NO_DEBT,
        governance_program_member=True,
        corporate_action_status=CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED,
        last_registry_close_date=date(2026, 7, 9),
        summary=(
            "Reviewed official packet: positive latest and four-year profitability, four due "
            "dividend periods, 75% payout for FY2025, positive own funds/no debt, clean annual "
            "audit and binding AGM dividend decision."
        ),
        citations=(
            ResearchCitation(
                kind=ResearchFactKind.FUNDAMENTALS,
                title="MOEX IFRS results for Q1 2026",
                url="https://www.moex.com/n100230",
            ),
            ResearchCitation(
                kind=ResearchFactKind.DIVIDENDS,
                title="MOEX AGM binding dividend decision for FY2025",
                url=_MOEX_AGM_URL,
            ),
            ResearchCitation(
                kind=ResearchFactKind.GOVERNANCE,
                title="MOEX AGM governance decisions for 2026",
                url=_MOEX_AGM_URL,
            ),
            ResearchCitation(
                kind=ResearchFactKind.CORPORATE_ACTIONS,
                title="MOEX reviewed AGM material-event coverage",
                url=_MOEX_AGM_URL,
            ),
        ),
    ),
    audit_status=IssuerAuditStatus.CLEAN,
    latest_period_profitable=True,
    positive_equity=True,
    governance_status=IssuerGovernanceStatus.CLEAR,
    event_coverage_through=_MOEX_REVIEWED_AT,
    documents=(
        IssuerSourceDocument(
            source_id="moex-security-identity",
            role=IssuerSourceRole.IDENTITY,
            title="MOEX security identity and dividend page",
            url="https://www.moex.com/a2656",
            publisher="Moscow Exchange",
            asset_id="MOEX",
            isin="RU000A0JR4A1",
            published_at=datetime(2026, 8, 16, 14, 55, tzinfo=UTC),
            retrieved_at=_MOEX_REVIEWED_AT,
            fact_effective_at=date(2026, 8, 16),
            content_sha256=(
                "7686e37b1e2e40a81a95f2f2bef2d914d3a4853a90f29f1da8408f20cfd1e8f5"
            ),
        ),
        IssuerSourceDocument(
            source_id="moex-q1-2026-financials",
            role=IssuerSourceRole.FINANCIALS,
            title="MOEX IFRS results for Q1 2026",
            url="https://www.moex.com/n100230",
            publisher="Moscow Exchange",
            asset_id="MOEX",
            isin="RU000A0JR4A1",
            published_at=datetime(2026, 5, 21, 6, 45, tzinfo=UTC),
            retrieved_at=_MOEX_REVIEWED_AT,
            fact_effective_at=date(2026, 3, 31),
            content_sha256="1fb30562a9918bc6b11ef335ec9fe470d79b24bfdb4537328b46248c02c1d043",
        ),
        IssuerSourceDocument(
            source_id="moex-fy2025-audit",
            role=IssuerSourceRole.AUDIT,
            title="Independent auditor report for MOEX FY2025",
            url="https://fs.moex.com/f/23629/summary-micex-rts-fs-fs-4q2025-eng.pdf",
            publisher="B1 Audit / Moscow Exchange",
            asset_id="MOEX",
            isin="RU000A0JR4A1",
            published_at=datetime(2026, 3, 5, 6, 45, tzinfo=UTC),
            retrieved_at=_MOEX_REVIEWED_AT,
            fact_effective_at=date(2025, 12, 31),
            content_sha256="f0a176f922985a4da07146f2f631a7ba15615fcfa638d3cdec08726ead7e9bd5",
        ),
        *tuple(
            IssuerSourceDocument(
                source_id=f"moex-fy2025-agm-{role.value}",
                role=role,
                title="MOEX AGM decisions for FY2025",
                url=_MOEX_AGM_URL,
                publisher="Moscow Exchange",
                asset_id="MOEX",
                isin="RU000A0JR4A1",
                published_at=datetime(2026, 6, 25, 15, 27, tzinfo=UTC),
                retrieved_at=_MOEX_REVIEWED_AT,
                fact_effective_at=date(2026, 6, 25),
                content_sha256=(
                    "1c4a8631aa2285b92bfe1e360131eeeef35dbd0193d551b720a20f8597d3487b"
                ),
            )
            for role in (
                IssuerSourceRole.DIVIDENDS,
                IssuerSourceRole.GOVERNANCE,
                IssuerSourceRole.CORPORATE_ACTIONS,
            )
        ),
        IssuerSourceDocument(
            source_id="moex-official-news-index",
            role=IssuerSourceRole.CORPORATE_ACTIONS,
            title="MOEX official news index reviewed for material events",
            url="https://www.moex.com/ru/news/",
            publisher="Moscow Exchange",
            asset_id="MOEX",
            isin="RU000A0JR4A1",
            published_at=datetime(2026, 8, 16, 14, 55, tzinfo=UTC),
            retrieved_at=_MOEX_REVIEWED_AT,
            fact_effective_at=date(2026, 8, 16),
            content_sha256=(
                "210f0073cd318a46bd39c569dbecba07a99124888567c43cf594f79bb68a4df1"
            ),
        ),
    ),
    events=(
        IssuerEventEvidence(
            event_id="moex-fy2025-dividend-declared",
            kind=IssuerEventKind.DIVIDEND_DECLARED,
            authority=IssuerDecisionAuthority.BINDING,
            source_id="moex-fy2025-agm-dividends",
            effective_from=date(2026, 6, 25),
            summary="AGM declared RUB 19.57 per share for FY2025.",
        ),
        IssuerEventEvidence(
            event_id="moex-fy2025-dividend-paid",
            kind=IssuerEventKind.DIVIDEND_PAID,
            authority=IssuerDecisionAuthority.HISTORICAL_FACT,
            source_id="moex-security-identity",
            effective_from=date(2026, 7, 9),
            summary="Official MOEX dividend history records the FY2025 distribution.",
        ),
    ),
)

REVIEWED_ISSUER_EVIDENCE = (MOEX_ISSUER_EVIDENCE_V2,)

__all__ = [
    "MOEX_DIVIDEND_RESEARCH",
    "MOEX_ISSUER_EVIDENCE_V2",
    "REVIEWED_ISSUER_EVIDENCE",
]
