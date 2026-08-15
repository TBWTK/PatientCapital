from collections.abc import Callable
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from patientcapital.domain.models import AllocationInput
from patientcapital.domain.planner import build_contribution_plan


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    contribution=st.integers(min_value=1, max_value=100_000),
    aaa_price=st.integers(min_value=1, max_value=2_000),
    bbb_price=st.integers(min_value=1, max_value=2_000),
    aaa_quantity=st.integers(min_value=0, max_value=500),
    bbb_quantity=st.integers(min_value=0, max_value=500),
    aaa_weight_percent=st.integers(min_value=0, max_value=100),
    fee_bps=st.integers(min_value=0, max_value=100),
    minimum_fee=st.integers(min_value=0, max_value=100),
)
def test_plan_never_exceeds_budget_and_never_worsens_total_drift(
    make_input: Callable[..., AllocationInput],
    contribution: int,
    aaa_price: int,
    bbb_price: int,
    aaa_quantity: int,
    bbb_quantity: int,
    aaa_weight_percent: int,
    fee_bps: int,
    minimum_fee: int,
) -> None:
    request = make_input(
        contribution=f"{contribution}.00",
        cash_buffer="0.00",
        aaa_price=f"{aaa_price}.00",
        bbb_price=f"{bbb_price}.00",
        aaa_quantity=aaa_quantity,
        bbb_quantity=bbb_quantity,
        aaa_weight=str(Decimal(aaa_weight_percent) / Decimal(100)),
        bbb_weight=str(Decimal(100 - aaa_weight_percent) / Decimal(100)),
        fee_rate=str(Decimal(fee_bps) / Decimal(10_000)),
        fee_minimum=f"{minimum_fee}.00",
    )

    plan = build_contribution_plan(request)

    assert plan.spent.amount <= plan.investable.amount
    assert plan.leftover.amount == plan.investable.amount - plan.spent.amount
    assert all(line.quantity == line.lots * line.lot_size for line in plan.lines)
    assert sum((abs(line.post_drift.amount) for line in plan.lines), Decimal()) <= sum(
        (abs(line.pre_drift.amount) for line in plan.lines), Decimal()
    )
    assert plan == build_contribution_plan(request)
