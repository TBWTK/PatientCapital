from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.api.app import create_app
from patientcapital.config import Settings
from patientcapital.transaction_intake.image import ExtractedImageText
from tests.integration.conftest import TEST_DATABASE_URL
from tests.integration.helpers import post_price, put_asset, put_profile

OCR_TEXT = """
Закрыть 13 августа 2026 · 16:34
Покупка 7 облигаций ОФЗ 26226
Количество 7 шт
Цена покупки 992,04 ₽
НКД 195,16 ₽
Комиссия 9? 3,47 ₽
"""


class StaticImageExtractor:
    def extract(self, content: bytes, *, declared_content_type: str) -> ExtractedImageText:
        assert content == b"synthetic-jpeg"
        assert declared_content_type == "image/jpeg"
        return ExtractedImageText(
            text=OCR_TEXT,
            media_type="image/jpeg",
            width=1178,
            height=2560,
            extractor_version="static-ocr-v1",
        )


def _client() -> TestClient:
    return TestClient(
        create_app(
            Settings(database_url=TEST_DATABASE_URL, app_env="test"),
            image_text_extractor=StaticImageExtractor(),
        )
    )


def _seed(client: TestClient) -> None:
    put_profile(client)
    put_asset(client, "SU26226RMFS9", name="ОФЗ 26226", target_weight="1")
    post_price(client, "SU26226RMFS9", "994.87")


def _confirmed_transaction() -> dict[str, object]:
    return {
        "idempotency_key": "draft-confirmed-buy-26226",
        "asset_id": "SU26226RMFS9",
        "side": "BUY",
        "quantity": 7,
        "unit_price": "992.04",
        "accrued_interest_total": "195.16",
        "fee": "3.47",
        "currency": "RUB",
        "occurred_at": "2026-08-13T16:34:00+03:00",
        "note": "Подтверждено по чеку T-Инвестиций",
    }


def test_text_creates_unconfirmed_draft_and_exact_confirmation_creates_one_event() -> None:
    with _client() as client:
        _seed(client)
        created = client.post("/v1/transaction-drafts/text", json={"text": OCR_TEXT})
        assert created.status_code == 201, created.text
        draft = created.json()
        assert draft["status"] == "unconfirmed"
        assert draft["source_kind"] == "text"
        assert draft["extractor_version"] == "transaction-text-ru-v1"
        assert draft["fields"] == {
            "side": "BUY",
            "asset_id": "SU26226RMFS9",
            "asset_name": "ОФЗ 26226",
            "quantity": 7,
            "unit_price": "992.04",
            "accrued_interest_total": "195.16",
            "fee": "3.47",
            "currency": "RUB",
            "occurred_at": "2026-08-13T16:34:00+03:00",
        }
        assert draft["unknown_fields"] == []
        assert draft["decision"] is None

        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
        engine.dispose()

        payload = {
            "expected_version": 1,
            "decision": "confirm",
            "transaction": _confirmed_transaction(),
        }
        confirmed = client.post(
            f"/v1/transaction-drafts/{draft['id']}/decisions", json=payload
        )
        assert confirmed.status_code == 201, confirmed.text
        result = confirmed.json()
        assert result["status"] == "confirmed"
        assert result["decision"]["transaction"]["quantity"] == 7
        assert result["decision"]["transaction"]["accrued_interest_total"] == "195.16"

        replay = client.post(
            f"/v1/transaction-drafts/{draft['id']}/decisions", json=payload
        )
        assert replay.status_code == 200
        assert replay.json() == result

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transaction_drafts")) == 1
        assert connection.scalar(text("SELECT count(*) FROM transaction_draft_decisions")) == 1
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 1
    engine.dispose()


def test_image_upload_uses_bounded_extractor_and_still_only_creates_draft() -> None:
    with _client() as client:
        _seed(client)
        response = client.post(
            "/v1/transaction-drafts/image",
            files={"file": ("receipt.jpg", b"synthetic-jpeg", "image/jpeg")},
        )

        assert response.status_code == 201, response.text
        draft = response.json()
        assert draft["source_kind"] == "image"
        assert draft["status"] == "unconfirmed"
        assert draft["extractor_version"] == "static-ocr-v1"
        assert draft["source_metadata"] == {
            "media_type": "image/jpeg",
            "width": 1178,
            "height": 2560,
        }
        assert draft["fields"]["quantity"] == 7
        assert len(cast(str, draft["source_sha256"])) == 64

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
    engine.dispose()


def test_incomplete_draft_cannot_be_confirmed_without_exact_transaction() -> None:
    with _client() as client:
        _seed(client)
        created = client.post(
            "/v1/transaction-drafts/text", json={"text": "Купил ОФЗ 26226"}
        )
        draft = created.json()
        assert {"quantity", "unit_price", "fee", "occurred_at"}.issubset(
            set(draft["unknown_fields"])
        )

        blocked = client.post(
            f"/v1/transaction-drafts/{draft['id']}/decisions",
            json={"expected_version": 1, "decision": "confirm", "transaction": None},
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_advanced_manual_input_creates_draft_before_confirmation() -> None:
    with _client() as client:
        _seed(client)
        transaction = _confirmed_transaction()
        transaction.pop("idempotency_key")
        response = client.post("/v1/transaction-drafts/manual", json=transaction)

        assert response.status_code == 201
        assert response.json()["status"] == "unconfirmed"
        assert response.json()["source_kind"] == "manual"

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
    engine.dispose()
