import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

import patientcapital.evals.gigachat as gigachat_eval
from patientcapital.evals.gigachat import (
    DEFAULT_CORPUS,
    _parse_args,
    evaluate_provider,
    load_corpus,
)
from patientcapital.providers.gigachat import (
    GigaChatConfig,
    GigaChatError,
    GigaChatProvider,
)


def _provider_for_corpus(*, corrupt_safety_case: bool) -> GigaChatProvider:
    corpus, _ = load_corpus(DEFAULT_CORPUS)
    explanations = {case.id: case for case in corpus.explanation_cases}
    intents = {case.text: case for case in corpus.intent_cases}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "auth.example":
            return httpx.Response(
                200,
                json={"access_token": "test-token", "expires_at": time.time() + 1800},
            )
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "GigaChat"}]})
        body = json.loads(request.content)
        user_payload = json.loads(body["messages"][1]["content"])
        if user_payload["task"] == "explain":
            explanation_case = next(
                item for item in explanations.values() if item.input == user_payload["input"]
            )
            output = explanation_case.expected.model_dump(mode="json") | {
                "summary": "План объяснён без изменения исходных фактов."
            }
        else:
            intent_case = intents[user_payload["request"]]
            output = intent_case.expected.model_dump(mode="json") | {
                "clarification": (
                    "Нужно уточнение или действие вне разрешённого контура."
                    if intent_case.expected.action in {"clarify", "out_of_scope"}
                    else ""
                )
            }
            if corrupt_safety_case and intent_case.id == "intent-17":
                output["action"] = "get_portfolio"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(output, ensure_ascii=False)}}],
                "model": "GigaChat:test-version",
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    config = GigaChatConfig(
        client_id=SecretStr("client"),
        api_key=SecretStr("secret"),
        scope="GIGACHAT_API_PERS",
        model="GigaChat",
        ca_bundle=Path("unused.crt"),
        auth_url="https://auth.example/api/v2/oauth",
        base_url="https://api.example/v1",
        timeout_seconds=1,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GigaChatProvider(config, client=client)


@pytest.mark.parametrize(
    ("corrupt_safety_case", "expected_admission"),
    [(False, True), (True, False)],
)
def test_eval_admits_only_complete_grounded_and_safe_corpus(
    corrupt_safety_case: bool,
    expected_admission: bool,
) -> None:
    corpus, corpus_hash = load_corpus(DEFAULT_CORPUS)
    provider = _provider_for_corpus(corrupt_safety_case=corrupt_safety_case)

    report = evaluate_provider(provider, corpus, corpus_hash, ["GigaChat"])

    assert report.admitted is expected_admission
    assert report.metrics.schema_rate == 1
    assert report.metrics.explanation_grounding_rate == 1
    assert len(report.cases) == 24
    serialized = report.model_dump_json()
    assert "test-token" not in serialized
    assert "SELECT * FROM transactions" not in serialized
    if corrupt_safety_case:
        assert report.metrics.intent_accuracy == 0.95
        assert report.metrics.safety_rate < 1
    else:
        assert report.metrics.intent_accuracy == 1
        assert report.metrics.safety_rate == 1


def test_eval_rejects_unavailable_model_without_completion_calls() -> None:
    corpus, corpus_hash = load_corpus(DEFAULT_CORPUS)
    provider = _provider_for_corpus(corrupt_safety_case=False)

    report = evaluate_provider(provider, corpus, corpus_hash, ["GigaChat-2"])

    assert report.admitted is False
    assert report.metrics.schema_rate == 0
    assert len(report.cases) == 24
    assert {case.error_code for case in report.cases} == {"GIGACHAT_MODEL_UNAVAILABLE"}


def test_eval_converts_provider_failures_to_sanitized_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, corpus_hash = load_corpus(DEFAULT_CORPUS)
    provider = _provider_for_corpus(corrupt_safety_case=False)

    def fail_completion(*args: object, **kwargs: object) -> None:
        raise GigaChatError("GIGACHAT_TIMEOUT", "sanitized")

    monkeypatch.setattr(provider, "structured_completion", fail_completion)
    report = evaluate_provider(provider, corpus, corpus_hash, ["GigaChat"])

    assert report.admitted is False
    assert {case.error_code for case in report.cases} == {"GIGACHAT_TIMEOUT"}
    assert "sanitized" not in report.model_dump_json()


def test_cli_parser_and_live_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["patientcapital-gigachat-eval", "--live", "--model", "GigaChat-2"],
    )
    args = _parse_args()
    assert args.live is True
    assert args.model == "GigaChat-2"

    monkeypatch.setattr(
        gigachat_eval,
        "_parse_args",
        lambda: argparse.Namespace(live=False),
    )
    with pytest.raises(SystemExit, match="Refusing external calls"):
        gigachat_eval.main()


def test_cli_writes_admitted_sanitized_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "nested" / "report.json"
    provider = _provider_for_corpus(corrupt_safety_case=False)
    monkeypatch.setattr(
        gigachat_eval,
        "_parse_args",
        lambda: argparse.Namespace(
            live=True,
            corpus=DEFAULT_CORPUS,
            output=output,
            model=None,
        ),
    )
    monkeypatch.setattr(
        GigaChatConfig,
        "from_settings",
        classmethod(lambda cls, settings: provider.config),
    )
    monkeypatch.setattr(gigachat_eval, "GigaChatProvider", lambda config: provider)

    with pytest.raises(SystemExit) as result:
        gigachat_eval.main()

    assert result.value.code == 0
    assert output.is_file()
    report_text = output.read_text(encoding="utf-8")
    assert '"admitted": true' in report_text
    assert "test-token" not in report_text
    assert "ADMITTED" in capsys.readouterr().out
