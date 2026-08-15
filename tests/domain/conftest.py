from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.models import (
    AllocationInput,
    Asset,
    FeePolicy,
    Position,
    PriceSnapshot,
    TargetAllocation,
)
from patientcapital.domain.money import Money


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


@pytest.fixture
def make_input(now: datetime) -> Callable[..., AllocationInput]:
    def factory(
        *,
        contribution: str = "10000.00",
        cash_buffer: str = "1000.00",
        aaa_price: str = "100.00",
        bbb_price: str = "100.00",
        aaa_quantity: int = 10,
        bbb_quantity: int = 20,
        aaa_weight: str = "0.50",
        bbb_weight: str = "0.50",
        aaa_lot: int = 1,
        bbb_lot: int = 1,
        fee_rate: str = "0.001",
        fee_minimum: str = "1.00",
        price_age: timedelta = timedelta(minutes=1),
        max_price_age: timedelta = timedelta(days=1),
    ) -> AllocationInput:
        assets = (
            Asset(id="AAA", name="Asset A", currency="RUB", lot_size=aaa_lot),
            Asset(id="BBB", name="Asset B", currency="RUB", lot_size=bbb_lot),
        )
        return AllocationInput(
            contribution=Money(Decimal(contribution), "RUB"),
            cash_buffer=Money(Decimal(cash_buffer), "RUB"),
            assets=assets,
            prices=(
                PriceSnapshot(
                    asset_id="AAA",
                    price=Decimal(aaa_price),
                    currency="RUB",
                    as_of=now - price_age,
                    max_age=max_price_age,
                    source="manual",
                ),
                PriceSnapshot(
                    asset_id="BBB",
                    price=Decimal(bbb_price),
                    currency="RUB",
                    as_of=now - price_age,
                    max_age=max_price_age,
                    source="manual",
                ),
            ),
            positions=(
                Position(asset_id="AAA", quantity=aaa_quantity),
                Position(asset_id="BBB", quantity=bbb_quantity),
            ),
            targets=(
                TargetAllocation(asset_id="AAA", weight=Decimal(aaa_weight)),
                TargetAllocation(asset_id="BBB", weight=Decimal(bbb_weight)),
            ),
            fee_policy=FeePolicy(
                rate=Decimal(fee_rate),
                minimum=Money(Decimal(fee_minimum), "RUB"),
            ),
            calculated_at=now,
        )

    return factory
