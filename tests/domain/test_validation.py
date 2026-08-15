from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.domain.models import AllocationInput, Position, TargetAllocation
from patientcapital.domain.money import Money
from patientcapital.domain.planner import build_contribution_plan


def test_weights_must_sum_to_one(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input(aaa_weight="0.60", bbb_weight="0.50")

    with pytest.raises(InvalidAllocationInput, match="TARGET_WEIGHT_SUM"):
        build_contribution_plan(request)


def test_every_position_must_have_target_and_price(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input()
    request = replace(
        request,
        targets=(TargetAllocation(asset_id="AAA", weight=request.targets[0].weight),),
    )

    with pytest.raises(InvalidAllocationInput, match="TARGET_ASSET_SET"):
        build_contribution_plan(request)


def test_stale_price_fails_loud(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input(price_age=timedelta(days=2), max_price_age=timedelta(days=1))

    with pytest.raises(InvalidAllocationInput, match=r"STALE_PRICE.*AAA"):
        build_contribution_plan(request)


def test_cross_currency_input_fails_before_planning(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input()
    wrong_price = replace(request.prices[0], currency="USD")
    request = replace(request, prices=(wrong_price, request.prices[1]))

    with pytest.raises(InvalidAllocationInput, match=r"CURRENCY_MISMATCH.*AAA"):
        build_contribution_plan(request)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda request: replace(
                request, calculated_at=request.calculated_at.replace(tzinfo=None)
            ),
            "INVALID_CALCULATION_TIME",
        ),
        (
            lambda request: replace(request, contribution=Money(Decimal("-1.00"), "RUB")),
            "NEGATIVE_CONTRIBUTION",
        ),
        (
            lambda request: replace(request, cash_buffer=Money(Decimal("-1.00"), "RUB")),
            "NEGATIVE_CASH_BUFFER",
        ),
        (
            lambda request: replace(request, cash_buffer=Money(Decimal("1.00"), "USD")),
            "CURRENCY_MISMATCH",
        ),
        (
            lambda request: replace(request, cash_buffer=Money(Decimal("10001.00"), "RUB")),
            "BUFFER_EXCEEDS_CONTRIBUTION",
        ),
        (
            lambda request: replace(request, assets=(*request.assets, request.assets[0])),
            "DUPLICATE_ASSET",
        ),
        (
            lambda request: replace(request, prices=(*request.prices, request.prices[0])),
            "DUPLICATE_PRICE",
        ),
        (
            lambda request: replace(request, positions=(*request.positions, request.positions[0])),
            "DUPLICATE_POSITION",
        ),
        (
            lambda request: replace(request, targets=(*request.targets, request.targets[0])),
            "DUPLICATE_TARGET",
        ),
        (
            lambda request: replace(request, assets=(), prices=(), positions=(), targets=()),
            "EMPTY_ASSET_SET",
        ),
        (lambda request: replace(request, prices=(request.prices[0],)), "PRICE_ASSET_SET"),
        (
            lambda request: replace(request, positions=(Position("UNKNOWN", 1),)),
            "POSITION_ASSET_SET",
        ),
        (
            lambda request: replace(
                request,
                prices=(
                    replace(
                        request.prices[0],
                        as_of=request.calculated_at + timedelta(seconds=1),
                    ),
                    request.prices[1],
                ),
            ),
            "FUTURE_PRICE",
        ),
    ],
)
def test_aggregate_validation_fails_with_stable_code(
    make_input: Callable[..., AllocationInput],
    mutate: Callable[[AllocationInput], AllocationInput],
    code: str,
) -> None:
    with pytest.raises(InvalidAllocationInput, match=code):
        build_contribution_plan(mutate(make_input()))
