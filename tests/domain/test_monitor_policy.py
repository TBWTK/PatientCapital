from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.monitoring.policy import (
    MONITOR_POLICY_VERSION,
    MonitorAssetObservation,
    evaluate_monitor_triggers,
)
from patientcapital.research.corpus import MOEX_DIVIDEND_RESEARCH
from patientcapital.research.models import CorporateActionStatus

NOW = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)


def observation(**overrides: object) -> MonitorAssetObservation:
    values: dict[str, object] = {
        "asset_id": "AAA",
        "quantity": 10,
        "previous_price": Decimal("100"),
        "current_price": Decimal("104"),
        "drift": Decimal("0.10"),
        "research": None,
    }
    values.update(overrides)
    return MonitorAssetObservation(**values)  # type: ignore[arg-type]


def test_monitor_policy_is_noop_below_registered_thresholds() -> None:
    assert evaluate_monitor_triggers((observation(),), calculated_at=NOW) == ()


def test_monitor_policy_emits_only_registered_drift_and_price_move_alerts() -> None:
    triggers = evaluate_monitor_triggers(
        (
            observation(
                previous_price=Decimal("100"),
                current_price=Decimal("112"),
                drift=Decimal("-0.20"),
            ),
        ),
        calculated_at=NOW,
    )

    assert [trigger.kind for trigger in triggers] == ["allocation_drift", "price_move"]
    assert all(trigger.policy_version == MONITOR_POLICY_VERSION for trigger in triggers)
    assert all(
        "SELL" not in trigger.message and "продать" not in trigger.message
        for trigger in triggers
    )
    assert triggers[0].evidence["absolute_drift"] == "0.20000000"
    assert triggers[1].evidence["absolute_move"] == "0.12000000"


def test_monitor_policy_emits_research_expiry_and_corporate_action_review() -> None:
    expiring = replace(MOEX_DIVIDEND_RESEARCH, max_age=MOEX_DIVIDEND_RESEARCH.max_age)
    material = replace(
        expiring,
        corporate_action_status=CorporateActionStatus.MATERIAL,
    )
    calculated_at = datetime(2027, 1, 20, 0, 0, tzinfo=UTC)

    triggers = evaluate_monitor_triggers(
        (observation(asset_id="MOEX", research=material),),
        calculated_at=calculated_at,
    )

    assert [trigger.kind for trigger in triggers] == [
        "research_expiring",
        "corporate_action_review",
    ]
    assert triggers[0].evidence["days_remaining"] == 23
    assert triggers[1].evidence["status"] == "material"


@pytest.mark.parametrize(
    "overrides",
    [
        {"asset_id": " "},
        {"quantity": -1},
        {"previous_price": Decimal("0")},
        {"current_price": Decimal("NaN")},
        {"drift": Decimal("Infinity")},
    ],
)
def test_monitor_observation_rejects_invalid_material_facts(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        observation(**overrides)

    assert captured.value.code == "INVALID_MONITOR_OBSERVATION"


def test_monitor_policy_requires_timezone_aware_calculation_time() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        evaluate_monitor_triggers(
            (observation(),),
            calculated_at=datetime(2026, 8, 16, 10, 0),
        )

    assert captured.value.code == "INVALID_MONITOR_TIME"
