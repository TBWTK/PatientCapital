"""Versioned registry of user-facing strategies admitted to proposal sets."""

# ruff: noqa: RUF001

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    summary: str
    why: str
    risk_note: str
    tradeoffs: tuple[str, ...]
    priority: int


FIVE_YEAR_CORE = StrategyDefinition(
    strategy_id="five_year_core",
    name="Основной план",
    summary="Вернуть портфель ближе к целевой структуре вашего риск-профиля.",
    why=(
        "Использует сохранённые риск-профиль, пятилетний горизонт, текущие позиции и реальные "
        "комиссии; покупает только целые доступные лоты из проверенного universe."
    ),
    risk_note=(
        "Стоимость активов может снижаться. Данные MOEX задержанные, поэтому цену нужно проверить "
        "у брокера перед фактической покупкой."
    ),
    tradeoffs=(
        "Следует долгосрочной структуре, а не краткосрочному рыночному сигналу.",
        "Не обещает доходность и не исполняет брокерскую заявку.",
    ),
    priority=100,
)


def admitted_strategies() -> tuple[StrategyDefinition, ...]:
    """Return only strategies backed by an implemented deterministic policy."""

    return (FIVE_YEAR_CORE,)
