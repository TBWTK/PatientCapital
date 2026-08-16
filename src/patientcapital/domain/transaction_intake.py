"""Deterministic extraction of transaction facts into an unconfirmed draft."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

PARSER_VERSION = "transaction-text-ru-v1"
MATERIAL_FIELDS = (
    "side",
    "asset_id",
    "quantity",
    "unit_price",
    "accrued_interest_total",
    "fee",
    "currency",
    "occurred_at",
)
_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_MONEY = r"(\d[\d\s\u00a0.]*(?:[,.]\d{1,8})?)"


@dataclass(frozen=True, slots=True)
class KnownAsset:
    asset_id: str
    name: str
    currency: str


@dataclass(frozen=True, slots=True)
class ParsedTransaction:
    side: str | None
    asset_id: str | None
    asset_name: str | None
    quantity: int | None
    unit_price: Decimal | None
    accrued_interest_total: Decimal | None
    fee: Decimal | None
    currency: str | None
    occurred_at: datetime | None
    unknown_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    field_confidence: dict[str, Decimal]


def _normalized(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", value).casefold().replace("ё", "\u0435").split()
    )


def _decimal(value: str) -> Decimal | None:
    compact = value.replace("\u00a0", "").replace(" ", "")
    if "," in compact:
        compact = compact.replace(".", "").replace(",", ".")
    try:
        result = Decimal(compact)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _last_money(line: str) -> Decimal | None:
    matches = re.findall(_MONEY, line)
    return _decimal(matches[-1]) if matches else None


def _resolve_asset(text: str, assets: tuple[KnownAsset, ...]) -> tuple[KnownAsset | None, bool]:
    normalized = _normalized(text)
    matches: list[KnownAsset] = []
    ofz_numbers = set(re.findall(r"офз\s*[-—]?\s*(\d{5})", normalized))
    for asset in assets:
        asset_id = _normalized(asset.asset_id)
        name = _normalized(asset.name)
        name_numbers = set(re.findall(r"офз\s*[-—]?\s*(\d{5})", name))
        if asset_id in normalized or (name and name in normalized) or ofz_numbers & name_numbers:
            matches.append(asset)
    unique = {item.asset_id: item for item in matches}
    if len(unique) == 1:
        return next(iter(unique.values())), False
    return None, len(unique) > 1


def _extract_labeled_money(text: str, labels: tuple[str, ...]) -> Decimal | None:
    for raw_line in text.splitlines():
        line = _normalized(raw_line)
        if any(label in line for label in labels):
            value = _last_money(line)
            if value is not None:
                return value
    return None


def _extract_quantity(text: str) -> tuple[int | None, Decimal | None]:
    normalized = _normalized(text)
    patterns = (
        (r"количество\D{0,12}(\d+)\s*шт", Decimal("1.00")),
        (r"(?:покупка|продажа)\s+(\d+)\s+(?:облигац\w*|акци\w*|па\w*)", Decimal("0.95")),
        (r"(?:купил|купила|продал|продала)\s+(\d+)", Decimal("0.85")),
    )
    for pattern, confidence in patterns:
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1)), confidence
    return None, None


def _extract_unit_price(text: str) -> tuple[Decimal | None, Decimal | None]:
    normalized = _normalized(text)
    for pattern, confidence in (
        (rf"цена\s+покупки\D{{0,8}}{_MONEY}", Decimal("1.00")),
        (rf"(?:по|за\s+единицу)\s*{_MONEY}", Decimal("0.90")),
    ):
        match = re.search(pattern, normalized)
        if match:
            return _decimal(match.group(1)), confidence
    return None, None


def _extract_occurred_at(text: str, timezone: ZoneInfo) -> datetime | None:
    normalized = _normalized(text)
    month_names = "|".join(_MONTHS)
    match = re.search(
        rf"(\d{{1,2}})\s+({month_names})\s+(\d{{4}}).{{0,12}}?(\d{{1,2}}):(\d{{2}})",
        normalized,
    )
    if match is None:
        return None
    day, month_name, year, hour, minute = match.groups()
    try:
        return datetime(
            int(year),
            _MONTHS[month_name],
            int(day),
            int(hour),
            int(minute),
            tzinfo=timezone,
        )
    except ValueError:
        return None


def parse_transaction_text(
    text: str,
    assets: tuple[KnownAsset, ...],
    *,
    timezone: ZoneInfo,
) -> ParsedTransaction:
    """Extract only explicit facts; ambiguity and absence remain visible."""

    normalized = _normalized(text)
    buy = bool(re.search(r"\b(?:покупка|купил|купила|куплено)\b", normalized))
    sell = bool(re.search(r"\b(?:продажа|продал|продала|продано)\b", normalized))
    conflicts: list[str] = []
    side: str | None = None
    if buy and sell:
        conflicts.append("side: одновременно распознаны BUY и SELL")
    elif buy:
        side = "BUY"
    elif sell:
        side = "SELL"

    asset, asset_conflict = _resolve_asset(text, assets)
    if asset_conflict:
        conflicts.append("asset_id: найдено несколько подходящих инструментов")
    quantity, quantity_confidence = _extract_quantity(text)
    unit_price, price_confidence = _extract_unit_price(text)
    accrued_interest = _extract_labeled_money(text, ("нкд",))
    fee = _extract_labeled_money(text, ("комиссия",))
    occurred_at = _extract_occurred_at(text, timezone)
    currency = asset.currency if asset is not None else ("RUB" if "₽" in text else None)

    values: dict[str, object | None] = {
        "side": side,
        "asset_id": asset.asset_id if asset else None,
        "quantity": quantity,
        "unit_price": unit_price,
        "accrued_interest_total": accrued_interest,
        "fee": fee,
        "currency": currency,
        "occurred_at": occurred_at,
    }
    confidence = {
        "side": Decimal("1.00") if side is not None else Decimal("0.00"),
        "asset_id": Decimal("1.00") if asset is not None else Decimal("0.00"),
        "quantity": quantity_confidence or Decimal("0.00"),
        "unit_price": price_confidence or Decimal("0.00"),
        "accrued_interest_total": (
            Decimal("1.00") if accrued_interest is not None else Decimal("0.00")
        ),
        "fee": Decimal("1.00") if fee is not None else Decimal("0.00"),
        "currency": Decimal("1.00") if currency is not None else Decimal("0.00"),
        "occurred_at": Decimal("1.00") if occurred_at is not None else Decimal("0.00"),
    }
    return ParsedTransaction(
        side=side,
        asset_id=asset.asset_id if asset else None,
        asset_name=asset.name if asset else None,
        quantity=quantity,
        unit_price=unit_price,
        accrued_interest_total=accrued_interest,
        fee=fee,
        currency=currency,
        occurred_at=occurred_at,
        unknown_fields=tuple(field for field in MATERIAL_FIELDS if values[field] is None),
        conflicts=tuple(conflicts),
        field_confidence=confidence,
    )
