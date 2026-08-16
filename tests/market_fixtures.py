from datetime import datetime, timedelta
from decimal import Decimal

from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketLiquidityEvidence,
)


def admitted_liquidity(kind: InstrumentKind, *, observed_at: datetime) -> MarketLiquidityEvidence:
    turnover = {
        InstrumentKind.OFZ: Decimal("100000000"),
        InstrumentKind.EQUITY_INDEX_FUND: Decimal("10000000"),
        InstrumentKind.DIVIDEND_STOCK: Decimal("100000000"),
        InstrumentKind.PUBLIC_EQUITY: Decimal("100000000"),
    }[kind]
    return MarketLiquidityEvidence(
        policy_version="market-liquidity-v2",
        observed_at=observed_at,
        max_age=timedelta(days=4),
        security_status="active",
        observations=tuple(
            LiquidityObservation(
                session_date=observed_at.date() - timedelta(days=index + 1),
                turnover_rub=turnover,
                trades=1000,
                bid=Decimal("100"),
                offer=Decimal("100.4"),
            )
            for index in range(20)
        ),
        source_url="https://iss.moex.com/iss/history/test",
    )
