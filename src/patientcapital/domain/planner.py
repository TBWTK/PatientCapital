"""Deterministic, lot-aware allocation of a new portfolio contribution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.domain.models import (
    AllocationInput,
    Asset,
    PlanLine,
    PlanReason,
    PriceSnapshot,
    RecommendationPlan,
)
from patientcapital.domain.money import Money, quantize_minor

ALGORITHM_VERSION = "contribution-greedy-v1"
_WEIGHT_TOLERANCE = Decimal("0.000001")
__all__ = ["PlanReason", "build_contribution_plan"]


@dataclass(frozen=True, slots=True)
class _ValidatedInput:
    request: AllocationInput
    currency: str
    assets: dict[str, Asset]
    prices: dict[str, PriceSnapshot]
    positions: dict[str, int]
    targets: dict[str, Decimal]


def _unique_by_id[T](items: tuple[T, ...], key: Any, code: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in items:
        identifier = key(item)
        if identifier in result:
            raise InvalidAllocationInput(code, f"duplicate id {identifier}")
        result[identifier] = item
    return result


def _validate(request: AllocationInput) -> _ValidatedInput:
    currency = request.contribution.currency
    if request.calculated_at.tzinfo is None or request.calculated_at.utcoffset() is None:
        raise InvalidAllocationInput(
            "INVALID_CALCULATION_TIME", "calculated_at must be timezone-aware"
        )
    if request.contribution.amount < 0:
        raise InvalidAllocationInput("NEGATIVE_CONTRIBUTION", "contribution must be non-negative")
    if request.cash_buffer.amount < 0:
        raise InvalidAllocationInput("NEGATIVE_CASH_BUFFER", "cash buffer must be non-negative")
    if request.cash_buffer.currency != currency:
        raise InvalidAllocationInput("CURRENCY_MISMATCH", "cash buffer differs from contribution")
    if request.fee_policy.minimum.currency != currency:
        raise InvalidAllocationInput("CURRENCY_MISMATCH", "fee policy differs from contribution")
    if request.cash_buffer.amount > request.contribution.amount:
        raise InvalidAllocationInput(
            "BUFFER_EXCEEDS_CONTRIBUTION", "cash buffer exceeds contribution"
        )

    assets = _unique_by_id(request.assets, lambda item: item.id, "DUPLICATE_ASSET")
    prices = _unique_by_id(request.prices, lambda item: item.asset_id, "DUPLICATE_PRICE")
    positions_raw = _unique_by_id(
        request.positions, lambda item: item.asset_id, "DUPLICATE_POSITION"
    )
    targets_raw = _unique_by_id(request.targets, lambda item: item.asset_id, "DUPLICATE_TARGET")
    asset_ids = set(assets)
    if not asset_ids:
        raise InvalidAllocationInput("EMPTY_ASSET_SET", "at least one asset is required")
    if set(prices) != asset_ids:
        raise InvalidAllocationInput("PRICE_ASSET_SET", "every asset needs exactly one price")
    if set(targets_raw) != asset_ids:
        raise InvalidAllocationInput("TARGET_ASSET_SET", "every asset needs exactly one target")
    if not set(positions_raw).issubset(asset_ids):
        raise InvalidAllocationInput("POSITION_ASSET_SET", "position references an unknown asset")

    positions = {
        asset_id: positions_raw[asset_id].quantity if asset_id in positions_raw else 0
        for asset_id in asset_ids
    }
    targets = {asset_id: targets_raw[asset_id].weight for asset_id in asset_ids}
    if abs(sum(targets.values(), Decimal()) - Decimal(1)) > _WEIGHT_TOLERANCE:
        raise InvalidAllocationInput("TARGET_WEIGHT_SUM", "target weights must sum to one")

    for asset_id, asset in assets.items():
        price = prices[asset_id]
        if asset.currency != currency or price.currency != currency:
            raise InvalidAllocationInput(
                "CURRENCY_MISMATCH",
                f"asset/price {asset_id} must use contribution currency {currency}",
            )
        if price.as_of > request.calculated_at:
            raise InvalidAllocationInput("FUTURE_PRICE", f"price for {asset_id} is from the future")
        if request.calculated_at - price.as_of > price.max_age:
            raise InvalidAllocationInput("STALE_PRICE", f"price for {asset_id} is stale")

    return _ValidatedInput(request, currency, assets, prices, positions, targets)


def _money(value: Decimal, currency: str) -> Money:
    return Money.calculated(value, currency)


def _gross(price: Decimal, quantity: int) -> Decimal:
    return quantize_minor(price * Decimal(quantity))


def _fee(gross: Decimal, request: AllocationInput) -> Decimal:
    if gross == 0:
        return Decimal("0.00")
    variable = quantize_minor(gross * request.fee_policy.rate)
    return max(variable, request.fee_policy.minimum.amount)


def _canonical_hash(validated: _ValidatedInput) -> str:
    request = validated.request

    def decimal(value: Decimal) -> str:
        return format(value, "f")

    payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "calculated_at": request.calculated_at.isoformat(),
        "contribution": [decimal(request.contribution.amount), request.contribution.currency],
        "cash_buffer": [decimal(request.cash_buffer.amount), request.cash_buffer.currency],
        "fee": [decimal(request.fee_policy.rate), decimal(request.fee_policy.minimum.amount)],
        "assets": [
            [asset.id, asset.name, asset.currency, asset.lot_size]
            for asset in sorted(validated.assets.values(), key=lambda item: item.id)
        ],
        "prices": [
            [
                price.asset_id,
                decimal(price.price),
                price.currency,
                price.as_of.isoformat(),
                price.max_age.total_seconds(),
                price.source,
            ]
            for price in sorted(validated.prices.values(), key=lambda item: item.asset_id)
        ],
        "positions": sorted(validated.positions.items()),
        "targets": [[key, decimal(value)] for key, value in sorted(validated.targets.items())],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def build_contribution_plan(request: AllocationInput) -> RecommendationPlan:
    """Build an immutable plan that only buys lots which reduce target-value drift."""

    validated = _validate(request)
    currency = validated.currency
    investable_amount = request.contribution.amount - request.cash_buffer.amount
    investable = Money(investable_amount, currency)

    current_values = {
        asset_id: _gross(validated.prices[asset_id].price, validated.positions[asset_id])
        for asset_id in validated.assets
    }
    target_base = sum(current_values.values(), Decimal()) + investable_amount
    target_values = {
        asset_id: quantize_minor(target_base * validated.targets[asset_id])
        for asset_id in validated.assets
    }
    lots = dict.fromkeys(validated.assets, 0)
    gross_by_asset = dict.fromkeys(validated.assets, Decimal("0.00"))
    fee_by_asset = dict.fromkeys(validated.assets, Decimal("0.00"))
    spent = Decimal("0.00")

    while True:
        candidates: list[tuple[Decimal, str, Decimal, Decimal, Decimal]] = []
        for asset_id in sorted(validated.assets):
            asset = validated.assets[asset_id]
            price = validated.prices[asset_id].price
            old_gross = gross_by_asset[asset_id]
            old_fee = fee_by_asset[asset_id]
            new_gross = _gross(price, (lots[asset_id] + 1) * asset.lot_size)
            new_fee = _fee(new_gross, request)
            incremental_spend = (new_gross + new_fee) - (old_gross + old_fee)
            if spent + incremental_spend > investable_amount:
                continue

            before_value = current_values[asset_id] + old_gross
            after_value = current_values[asset_id] + new_gross
            before_abs = abs(target_values[asset_id] - before_value)
            after_abs = abs(target_values[asset_id] - after_value)
            improvement = before_abs - after_abs
            if improvement <= 0:
                continue
            remaining_drift = target_values[asset_id] - before_value
            candidates.append((remaining_drift, asset_id, incremental_spend, new_gross, new_fee))

        if not candidates:
            break
        _, selected, incremental_spend, new_gross, new_fee = max(
            candidates, key=lambda item: (item[0], item[1])
        )
        lots[selected] += 1
        gross_by_asset[selected] = new_gross
        fee_by_asset[selected] = new_fee
        spent += incremental_spend

    lines: list[PlanLine] = []
    for asset_id in sorted(validated.assets):
        selected_lots = lots[asset_id]
        if selected_lots == 0:
            continue
        asset = validated.assets[asset_id]
        quantity = selected_lots * asset.lot_size
        gross = gross_by_asset[asset_id]
        fee = fee_by_asset[asset_id]
        current = current_values[asset_id]
        target = target_values[asset_id]
        lines.append(
            PlanLine(
                asset_id=asset_id,
                lots=selected_lots,
                lot_size=asset.lot_size,
                quantity=quantity,
                unit_price=validated.prices[asset_id].price,
                current_value=_money(current, currency),
                target_value=_money(target, currency),
                pre_drift=_money(current - target, currency),
                post_drift=_money(current + gross - target, currency),
                gross=_money(gross, currency),
                fee=_money(fee, currency),
                total=_money(gross + fee, currency),
            )
        )

    gross_total = sum(gross_by_asset.values(), Decimal())
    fee_total = sum(fee_by_asset.values(), Decimal())
    spent_total = gross_total + fee_total
    if lines:
        reason = PlanReason.ALLOCATED
    elif investable_amount == 0:
        reason = PlanReason.ZERO_INVESTABLE
    else:
        reason = PlanReason.BUDGET_BELOW_ANY_LOT

    return RecommendationPlan(
        algorithm_version=ALGORITHM_VERSION,
        input_hash=_canonical_hash(validated),
        calculated_at=request.calculated_at,
        investable=investable,
        gross=_money(gross_total, currency),
        fees=_money(fee_total, currency),
        spent=_money(spent_total, currency),
        leftover=_money(investable_amount - spent_total, currency),
        reason=reason,
        lines=tuple(lines),
    )
