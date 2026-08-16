"""Pure threshold/event policy for portfolio observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.research.models import CorporateActionStatus, DividendResearchEvidence

MONITOR_POLICY_VERSION = "monitor-threshold-v1"
_DRIFT_THRESHOLD = Decimal("0.15000000")
_PRICE_MOVE_THRESHOLD = Decimal("0.10000000")
_RESEARCH_EXPIRY_DAYS = 30

MonitorTriggerKind = Literal[
    "allocation_drift",
    "price_move",
    "research_expiring",
    "corporate_action_review",
]


@dataclass(frozen=True, slots=True)
class MonitorAssetObservation:
    asset_id: str
    quantity: int
    previous_price: Decimal
    current_price: Decimal
    drift: Decimal
    research: DividendResearchEvidence | None

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise InvalidAllocationInput(
                "INVALID_MONITOR_OBSERVATION", "asset id is required"
            )
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity < 0
        ):
            raise InvalidAllocationInput(
                "INVALID_MONITOR_OBSERVATION", "quantity must be a non-negative integer"
            )
        for name, value, positive in (
            ("previous_price", self.previous_price, True),
            ("current_price", self.current_price, True),
            ("drift", self.drift, False),
        ):
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or (positive and value <= 0)
            ):
                raise InvalidAllocationInput(
                    "INVALID_MONITOR_OBSERVATION", f"{name} is invalid"
                )


@dataclass(frozen=True, slots=True)
class MonitorTrigger:
    policy_version: str
    kind: MonitorTriggerKind
    severity: Literal["info", "warning"]
    asset_id: str
    title: str
    message: str
    evidence: dict[str, object]


def evaluate_monitor_triggers(
    observations: tuple[MonitorAssetObservation, ...],
    *,
    calculated_at: datetime,
) -> tuple[MonitorTrigger, ...]:
    if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
        raise InvalidAllocationInput(
            "INVALID_MONITOR_TIME", "monitor calculation time must be timezone-aware"
        )
    triggers: list[MonitorTrigger] = []
    for observation in observations:
        if observation.quantity == 0:
            continue
        absolute_drift = abs(observation.drift)
        if absolute_drift >= _DRIFT_THRESHOLD:
            triggers.append(
                MonitorTrigger(
                    policy_version=MONITOR_POLICY_VERSION,
                    kind="allocation_drift",
                    severity="info",
                    asset_id=observation.asset_id,
                    title="Отклонение портфеля требует проверки",
                    message=(
                        f"Доля {observation.asset_id} отклонилась от цели не менее чем на "
                        "15 п.п. Откройте новый расчёт пополнения; операция не создана."
                    ),
                    evidence={
                        "drift": str(observation.drift.quantize(Decimal("0.00000001"))),
                        "absolute_drift": str(absolute_drift.quantize(Decimal("0.00000001"))),
                        "threshold": str(_DRIFT_THRESHOLD),
                    },
                )
            )
        move = (observation.current_price / observation.previous_price - Decimal("1")).quantize(
            Decimal("0.00000001")
        )
        absolute_move = abs(move)
        if absolute_move >= _PRICE_MOVE_THRESHOLD:
            triggers.append(
                MonitorTrigger(
                    policy_version=MONITOR_POLICY_VERSION,
                    kind="price_move",
                    severity="warning",
                    asset_id=observation.asset_id,
                    title="Цена заметно изменилась",
                    message=(
                        f"Цена {observation.asset_id} изменилась не менее чем на 10% относительно "
                        "предыдущего снимка. Проверьте контекст; операция не создана."
                    ),
                    evidence={
                        "previous_price": str(observation.previous_price),
                        "current_price": str(observation.current_price),
                        "move": str(move),
                        "absolute_move": str(absolute_move),
                        "threshold": str(_PRICE_MOVE_THRESHOLD),
                    },
                )
            )
        research = observation.research
        if research is None:
            continue
        expires_at = research.observed_at + research.max_age
        days_remaining = (expires_at - calculated_at).days
        if 0 <= days_remaining <= _RESEARCH_EXPIRY_DAYS:
            triggers.append(
                MonitorTrigger(
                    policy_version=MONITOR_POLICY_VERSION,
                    kind="research_expiring",
                    severity="info",
                    asset_id=observation.asset_id,
                    title="Research evidence скоро устареет",
                    message=(
                        f"Evidence {observation.asset_id} требует reviewed refresh в течение "
                        f"{days_remaining} дн.; операция не создана."
                    ),
                    evidence={
                        "research_policy_version": research.policy_version,
                        "expires_at": expires_at.isoformat(),
                        "days_remaining": days_remaining,
                    },
                )
            )
        if (
            research.corporate_action_status
            is not CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED
        ):
            triggers.append(
                MonitorTrigger(
                    policy_version=MONITOR_POLICY_VERSION,
                    kind="corporate_action_review",
                    severity="warning",
                    asset_id=observation.asset_id,
                    title="Нужно проверить корпоративное событие",
                    message=(
                        f"Corporate-action status {observation.asset_id} больше не является "
                        "clear. Требуется ручная проверка; операция не создана."
                    ),
                    evidence={
                        "research_policy_version": research.policy_version,
                        "status": research.corporate_action_status.value,
                    },
                )
            )
    return tuple(triggers)
