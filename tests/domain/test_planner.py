from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal

from patientcapital.domain.models import AllocationInput
from patientcapital.domain.planner import PlanReason, build_contribution_plan


def test_known_contribution_plan_is_explainable_and_budget_safe(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input()

    plan = build_contribution_plan(request)

    assert [(line.asset_id, line.lots, line.quantity) for line in plan.lines] == [
        ("AAA", 49, 49),
        ("BBB", 40, 40),
    ]
    assert plan.investable.amount == Decimal("9000.00")
    assert plan.gross.amount == Decimal("8900.00")
    assert plan.fees.amount == Decimal("8.90")
    assert plan.spent.amount == Decimal("8908.90")
    assert plan.leftover.amount == Decimal("91.10")
    assert plan.reason is PlanReason.ALLOCATED
    assert plan.algorithm_version == "contribution-greedy-v1"
    assert len(plan.input_hash) == 64

    aaa, bbb = plan.lines
    assert aaa.pre_drift.amount == Decimal("-5000.00")
    assert aaa.post_drift.amount == Decimal("-100.00")
    assert bbb.pre_drift.amount == Decimal("-4000.00")
    assert bbb.post_drift.amount == Decimal("0.00")


def test_minimum_commission_is_charged_once_per_asset_order(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input(
        contribution="100.00",
        cash_buffer="0.00",
        aaa_price="30.00",
        bbb_price="1000.00",
        aaa_quantity=0,
        bbb_quantity=0,
        aaa_weight="1.00",
        bbb_weight="0.00",
        fee_rate="0.001",
        fee_minimum="5.00",
    )

    plan = build_contribution_plan(request)

    assert [(line.asset_id, line.quantity) for line in plan.lines] == [("AAA", 3)]
    assert plan.gross.amount == Decimal("90.00")
    assert plan.fees.amount == Decimal("5.00")
    assert plan.leftover.amount == Decimal("5.00")


def test_budget_below_any_improving_lot_returns_visible_reason(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input(
        contribution="30.00",
        cash_buffer="0.00",
        aaa_price="30.00",
        bbb_price="1000.00",
        aaa_quantity=0,
        bbb_quantity=0,
        aaa_weight="1.00",
        bbb_weight="0.00",
        fee_minimum="5.00",
    )

    plan = build_contribution_plan(request)

    assert plan.lines == ()
    assert plan.reason is PlanReason.BUDGET_BELOW_ANY_LOT
    assert plan.leftover.amount == Decimal("30.00")


def test_zero_investable_is_distinct_from_budget_below_a_lot(
    make_input: Callable[..., AllocationInput],
) -> None:
    zero = build_contribution_plan(make_input(contribution="0.00", cash_buffer="0.00"))
    balanced = build_contribution_plan(
        make_input(
            contribution="100.00",
            cash_buffer="0.00",
            aaa_quantity=10,
            bbb_quantity=10,
            aaa_weight="0.50",
            bbb_weight="0.50",
            aaa_price="100.00",
            bbb_price="100.00",
            aaa_lot=100,
            bbb_lot=100,
        )
    )

    assert zero.reason is PlanReason.ZERO_INVESTABLE
    assert balanced.reason is PlanReason.BUDGET_BELOW_ANY_LOT


def test_same_input_produces_byte_equivalent_plan(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input()

    first = build_contribution_plan(request)
    second = build_contribution_plan(request)

    assert asdict(first) == asdict(second)


def test_planning_does_not_mutate_position_input(
    make_input: Callable[..., AllocationInput],
) -> None:
    request = make_input()
    before = request.positions

    build_contribution_plan(request)

    assert request.positions == before
