import base64
import json
import time
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from patientcapital.config import Settings
from patientcapital.providers.gigachat import (
    GigaChatConfig,
    GigaChatError,
    GigaChatProvider,
)


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


def _config() -> GigaChatConfig:
    return GigaChatConfig(
        client_id=SecretStr("client-id"),
        api_key=SecretStr("api-secret"),
        scope="GIGACHAT_API_PERS",
        model="GigaChat",
        ca_bundle=Path("not-used-by-mock.crt"),
        auth_url="https://auth.example/api/v2/oauth",
        base_url="https://api.example/v1",
        timeout_seconds=1,
    )


def test_structured_completion_uses_oauth_once_and_strict_schema() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "auth.example":
            expected = base64.b64encode(b"client-id:api-secret").decode()
            assert request.headers["Authorization"] == f"Basic {expected}"
            assert UUID(request.headers["RqUID"]).version == 4
            assert request.content == b"scope=GIGACHAT_API_PERS"
            return httpx.Response(
                200,
                json={"access_token": "sensitive-token", "expires_at": time.time() + 1800},
            )
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer sensitive-token"
        assert body["temperature"] == 0
        assert body["response_format"]["strict"] is True
        assert body["response_format"]["schema"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":"grounded"}'}}],
                "model": "GigaChat:test-version",
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GigaChatProvider(_config(), client=client)

    first = provider.structured_completion(
        ExampleOutput,
        system_prompt="Return only grounded data.",
        user_payload={"fact": "grounded"},
    )
    second = provider.structured_completion(
        ExampleOutput,
        system_prompt="Return only grounded data.",
        user_payload={"fact": "grounded"},
    )

    assert first.output.answer == "grounded"
    assert first.model == "GigaChat:test-version"
    assert len(first.response_hash) == 64
    assert second.output == first.output
    assert sum(request.url.host == "auth.example" for request in requests) == 1
    assert "sensitive-token" not in repr(first)


def test_transport_and_schema_failures_are_sanitized() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("raw timeout with api-secret", request=request)

    timeout_provider = GigaChatProvider(
        _config(), client=httpx.Client(transport=httpx.MockTransport(timeout_handler))
    )
    with pytest.raises(GigaChatError) as timeout:
        timeout_provider.list_models()
    assert timeout.value.code == "GIGACHAT_TIMEOUT"
    assert "api-secret" not in str(timeout.value)

    def malformed_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "auth.example":
            return httpx.Response(
                200,
                json={"access_token": "token", "expires_at": time.time() + 1800},
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":7}'}}],
                "model": "GigaChat:test-version",
                "usage": {},
            },
        )

    malformed_provider = GigaChatProvider(
        _config(), client=httpx.Client(transport=httpx.MockTransport(malformed_handler))
    )
    with pytest.raises(GigaChatError) as malformed:
        malformed_provider.structured_completion(
            ExampleOutput,
            system_prompt="strict",
            user_payload={},
        )
    assert malformed.value.code == "GIGACHAT_OUTPUT_SCHEMA_INVALID"
    assert '{"answer":7}' not in str(malformed.value)


def test_settings_require_credentials_but_keep_them_secret() -> None:
    missing = Settings(gigachat_client_id=None, gigachat_api_key=None)
    with pytest.raises(GigaChatError) as error:
        GigaChatConfig.from_settings(missing)
    assert error.value.code == "GIGACHAT_CREDENTIALS_MISSING"

    configured = Settings(
        gigachat_client_id=SecretStr("client"),
        gigachat_api_key=SecretStr("private-api-key"),
    )
    config = GigaChatConfig.from_settings(configured)
    assert "private-api-key" not in repr(config)


def test_preencoded_authorization_key_is_not_encoded_twice() -> None:
    authorization_key = base64.b64encode(b"client-id:actual-secret").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "auth.example":
            assert request.headers["Authorization"] == f"Basic {authorization_key}"
            return httpx.Response(
                200,
                json={"access_token": "token", "expires_at": time.time() + 1800},
            )
        return httpx.Response(200, json={"data": [{"id": "GigaChat"}]})

    config = _config().model_copy(update={"api_key": SecretStr(authorization_key)})
    provider = GigaChatProvider(config, client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert provider.list_models() == ["GigaChat"]


def test_missing_ca_bundle_fails_closed() -> None:
    with pytest.raises(GigaChatError) as error:
        GigaChatProvider(_config())
    assert error.value.code == "GIGACHAT_CA_BUNDLE_MISSING"


@pytest.mark.parametrize(
    ("handler_kind", "expected_code"),
    [
        ("connection", "GIGACHAT_CONNECTION_FAILED"),
        ("http", "GIGACHAT_HTTP_503"),
        ("auth_schema", "GIGACHAT_AUTH_SCHEMA_INVALID"),
        ("models_schema", "GIGACHAT_MODELS_SCHEMA_INVALID"),
    ],
)
def test_additional_provider_failures_are_sanitized(
    handler_kind: str,
    expected_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if handler_kind == "connection":
            raise httpx.ConnectError("raw secret detail", request=request)
        if handler_kind == "http":
            return httpx.Response(503, text="raw secret detail")
        if request.url.host == "auth.example":
            if handler_kind == "auth_schema":
                return httpx.Response(200, json={"unexpected": "raw secret detail"})
            return httpx.Response(
                200,
                json={
                    "access_token": "token",
                    "expires_at": (time.time() + 1800) * 1000,
                },
            )
        return httpx.Response(200, json={"unexpected": []})

    provider = GigaChatProvider(
        _config(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with provider, pytest.raises(GigaChatError) as error:
        provider.list_models()

    assert error.value.code == expected_code
    assert "raw secret detail" not in str(error.value)
