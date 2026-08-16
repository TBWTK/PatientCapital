from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

from patientcapital.application.errors import ApplicationError
from patientcapital.domain.transaction_intake import KnownAsset, parse_transaction_text
from patientcapital.transaction_intake.image import TesseractImageExtractor

ASSETS = (
    KnownAsset("SU26226RMFS9", "ОФЗ 26226", "RUB"),
    KnownAsset("EQMX", "ВИМ — Индекс МосБиржи", "RUB"),
)


def test_tinkoff_receipt_ocr_extracts_exact_material_fields() -> None:
    receipt = """
    Закрыть 13 августа 2026 · 16:34
    Покупка 7 облигаций ОФЗ 26226
    -7 139,44 ₽
    Количество 7 шт
    Цена покупки 992,04 ₽
    НКД 195,16 ₽
    Комиссия 9? 3,47 ₽
    2 сделки
    2 шт по 992,04 ₽
    5 шт по 992,04 ₽
    """

    parsed = parse_transaction_text(receipt, ASSETS, timezone=ZoneInfo("Europe/Moscow"))

    assert parsed.side == "BUY"
    assert parsed.asset_id == "SU26226RMFS9"
    assert parsed.asset_name == "ОФЗ 26226"
    assert parsed.quantity == 7
    assert parsed.unit_price == Decimal("992.04")
    assert parsed.accrued_interest_total == Decimal("195.16")
    assert parsed.fee == Decimal("3.47")
    assert parsed.currency == "RUB"
    assert parsed.occurred_at == datetime(
        2026, 8, 13, 16, 34, tzinfo=ZoneInfo("Europe/Moscow")
    )
    assert parsed.unknown_fields == ()
    assert parsed.conflicts == ()


def test_missing_year_stays_unknown_instead_of_using_current_year() -> None:
    parsed = parse_transaction_text(
        "Купил 7 ОФЗ 26226 по 992,04 ₽ 13 августа в 16:34, комиссия 3,47 ₽",
        ASSETS,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    assert parsed.occurred_at is None
    assert "occurred_at" in parsed.unknown_fields
    assert parsed.quantity == 7
    assert parsed.unit_price == Decimal("992.04")


def test_conflicting_side_is_visible_and_not_resolved_by_guessing() -> None:
    parsed = parse_transaction_text(
        "Покупка и продажа 2 ОФЗ 26226 по 990,00 ₽",
        ASSETS,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    assert parsed.side is None
    assert "side" in parsed.unknown_fields
    assert parsed.conflicts == ("side: одновременно распознаны BUY и SELL",)


def _png(width: int = 10, height: int = 10) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (width, height), color="white").save(stream, format="PNG")
    return stream.getvalue()


def test_image_intake_rejects_mime_magic_mismatch(tmp_path: Path) -> None:
    extractor = TesseractImageExtractor(temp_directory=tmp_path)

    with pytest.raises(ApplicationError, match="declared media type") as error:
        extractor.extract(_png(), declared_content_type="image/jpeg")

    assert error.value.code == "IMAGE_TYPE_MISMATCH"
    assert list(tmp_path.iterdir()) == []


def test_image_intake_rejects_oversized_bytes_and_pixels(tmp_path: Path) -> None:
    with pytest.raises(ApplicationError) as bytes_error:
        TesseractImageExtractor(max_bytes=10, temp_directory=tmp_path).extract(
            _png(), declared_content_type="image/png"
        )
    assert bytes_error.value.code == "UPLOAD_TOO_LARGE"

    with pytest.raises(ApplicationError) as pixels_error:
        TesseractImageExtractor(max_pixels=99, temp_directory=tmp_path).extract(
            _png(), declared_content_type="image/png"
        )
    assert pixels_error.value.code == "IMAGE_DIMENSIONS_EXCEEDED"
