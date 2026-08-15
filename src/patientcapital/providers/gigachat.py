"""Fail-closed GigaChat structured-output client used by the admission eval."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from patientcapital.config import Settings


class GigaChatError(RuntimeError):
    """Sanitized provider failure safe for reports and fallback decisions."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class GigaChatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: SecretStr
    api_key: SecretStr
    scope: str
    model: str
    ca_bundle: Path
    auth_url: str
    base_url: str
    timeout_seconds: float = Field(gt=0, le=120)

    @classmethod
    def from_settings(cls, settings: Settings) -> GigaChatConfig:
        if settings.gigachat_client_id is None or settings.gigachat_api_key is None:
            raise GigaChatError(
                "GIGACHAT_CREDENTIALS_MISSING",
                "client id and API key are required for the admission eval",
            )
        return cls(
            client_id=settings.gigachat_client_id,
            api_key=settings.gigachat_api_key,
            scope=settings.gigachat_scope,
            model=settings.gigachat_model,
            ca_bundle=settings.gigachat_ca_bundle,
            auth_url=settings.gigachat_auth_url,
            base_url=settings.gigachat_base_url,
            timeout_seconds=settings.gigachat_timeout_seconds,
        )


class _TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: SecretStr
    expires_at: int | float


class _ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str


class _ChatChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: _ChatMessage


class _ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[_ChatChoice] = Field(min_length=1)
    model: str
    usage: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class GigaChatCompletion[OutputT: BaseModel]:
    output: OutputT
    model: str
    usage: dict[str, int]
    latency_ms: int
    response_hash: str


class GigaChatProvider:
    """Minimal OAuth + JSON Schema adapter; raw responses and tokens are never logged."""

    def __init__(
        self,
        config: GigaChatConfig,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self._owns_client = client is None
        if client is None:
            if not config.ca_bundle.is_file():
                raise GigaChatError(
                    "GIGACHAT_CA_BUNDLE_MISSING",
                    "configured CA bundle does not exist",
                )
            tls_context = ssl.create_default_context(cafile=str(config.ca_bundle))
            client = httpx.Client(
                verify=tls_context,
                timeout=httpx.Timeout(config.timeout_seconds),
                headers={"Accept": "application/json"},
            )
        self._client = client
        self._access_token: SecretStr | None = None
        self._expires_at = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GigaChatProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _authorization_key(self) -> str:
        client_id = self.config.client_id.get_secret_value()
        api_key = self.config.api_key.get_secret_value()
        try:
            decoded = base64.b64decode(api_key, validate=True).decode()
            decoded_client_id, separator, _secret = decoded.partition(":")
            if separator and hmac.compare_digest(decoded_client_id, client_id):
                return api_key
        except (binascii.Error, UnicodeDecodeError):
            pass
        raw = f"{client_id}:{api_key}"
        return base64.b64encode(raw.encode()).decode()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            raise GigaChatError("GIGACHAT_TIMEOUT", "provider request timed out") from error
        except (httpx.ConnectError, httpx.NetworkError) as error:
            raise GigaChatError(
                "GIGACHAT_CONNECTION_FAILED", "provider connection failed"
            ) from error
        if response.status_code >= 400:
            raise GigaChatError(
                f"GIGACHAT_HTTP_{response.status_code}",
                "provider returned a non-success status",
            )
        return response

    def _token(self) -> str:
        if self._access_token is not None and time.time() < self._expires_at - 60:
            return self._access_token.get_secret_value()
        response = self._request(
            "POST",
            self.config.auth_url,
            headers={
                "Authorization": f"Basic {self._authorization_key()}",
                "RqUID": str(uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": self.config.scope},
        )
        try:
            token = _TokenResponse.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise GigaChatError(
                "GIGACHAT_AUTH_SCHEMA_INVALID",
                "OAuth response does not match the expected schema",
            ) from error
        expires_at = float(token.expires_at)
        if expires_at > 100_000_000_000:
            expires_at /= 1000
        self._access_token = token.access_token
        self._expires_at = expires_at
        return token.access_token.get_secret_value()

    def list_models(self) -> list[str]:
        response = self._request(
            "GET",
            f"{self.config.base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {self._token()}"},
        )
        try:
            payload = response.json()
            data = payload["data"]
            return [str(item["id"]) for item in data]
        except (KeyError, TypeError, ValueError) as error:
            raise GigaChatError(
                "GIGACHAT_MODELS_SCHEMA_INVALID",
                "models response does not match the expected schema",
            ) from error

    def structured_completion[OutputT: BaseModel](
        self,
        output_type: type[OutputT],
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_tokens: int = 1200,
    ) -> GigaChatCompletion[OutputT]:
        request_payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        user_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "schema": output_type.model_json_schema(mode="serialization"),
                "strict": True,
            },
        }
        started = time.perf_counter()
        response = self._request(
            "POST",
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
            json=request_payload,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        response_hash = hashlib.sha256(response.content).hexdigest()
        try:
            envelope = _ChatResponse.model_validate(response.json())
            output = output_type.model_validate_json(envelope.choices[0].message.content)
        except (ValueError, ValidationError, json.JSONDecodeError) as error:
            raise GigaChatError(
                "GIGACHAT_OUTPUT_SCHEMA_INVALID",
                "model output does not match the required JSON schema",
            ) from error
        return GigaChatCompletion(
            output=output,
            model=envelope.model,
            usage=envelope.usage,
            latency_ms=latency_ms,
            response_hash=response_hash,
        )
