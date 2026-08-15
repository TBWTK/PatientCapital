from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from patientcapital.domain.errors import CurrencyMismatch, InvalidAllocationInput, InvalidMoney
from patientcapital.domain.models import (
    Asset,
    FeePolicy,
    Position,
    PriceSnapshot,
    TargetAllocation,
)
from patientcapital.domain.money import Money, quantize_minor


def test_calculated_money_rounds_half_up_but_user_money_must_be_exact() -> None:
    assert quantize_minor(Decimal("1.005")) == Decimal("1.01")
    assert Money.calculated(Decimal("1.005"), "RUB") == Money(Decimal("1.01"), "RUB")
    assert Money.zero("RUB") == Money(Decimal("0.00"), "RUB")

    with pytest.raises(InvalidMoney):
        quantize_minor(Decimal("NaN"))
    with pytest.raises(CurrencyMismatch):
        _ = Money(Decimal("1.00"), "RUB") - Money(Decimal("1.00"), "USD")


@pytest.mark.parametrize(
    "build",
    [
        lambda: Asset(id="", name="A", currency="RUB", lot_size=1),
        lambda: Asset(id="A", name="", currency="RUB", lot_size=1),
        lambda: Asset(id="A", name="A", currency="RUB", lot_size=0),
        lambda: Asset(id="A", name="A", currency="RUB", lot_size=True),
        lambda: Position(asset_id="", quantity=0),
        lambda: Position(asset_id="A", quantity=-1),
        lambda: Position(asset_id="A", quantity=True),
        lambda: TargetAllocation(asset_id="", weight=Decimal("1")),
        lambda: TargetAllocation(asset_id="A", weight=Decimal("NaN")),
        lambda: TargetAllocation(asset_id="A", weight=Decimal("1.1")),
        lambda: FeePolicy(
            rate=Decimal("-0.1"), minimum=Money(Decimal("0.00"), "RUB")
        ),
        lambda: FeePolicy(
            rate=Decimal("1.1"), minimum=Money(Decimal("0.00"), "RUB")
        ),
        lambda: FeePolicy(
            rate=Decimal("0.1"), minimum=Money(Decimal("-1.00"), "RUB")
        ),
    ],
)
def test_models_reject_invalid_structural_values(build: Callable[[], object]) -> None:
    with pytest.raises(InvalidAllocationInput):
        build()


@pytest.mark.parametrize(
    "overrides",
    [
        {"asset_id": ""},
        {"source": ""},
        {"price": Decimal("0")},
        {"price": Decimal("NaN")},
        {"as_of": datetime(2026, 1, 1)},
        {"max_age": timedelta(0)},
    ],
)
def test_price_snapshot_rejects_incomplete_or_ambiguous_values(
    overrides: dict[str, object],
) -> None:
    values: dict[str, Any] = {
        "asset_id": "AAA",
        "price": Decimal("10"),
        "currency": "RUB",
        "as_of": datetime(2026, 1, 1, tzinfo=UTC),
        "max_age": timedelta(days=1),
        "source": "manual",
    }
    values.update(overrides)

    with pytest.raises(InvalidAllocationInput):
        PriceSnapshot(**values)
