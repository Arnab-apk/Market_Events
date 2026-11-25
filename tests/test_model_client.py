"""Model I/O accounting without depending on live inference or network access."""

import json
from pathlib import Path

import pytest
import requests

from market_events.config import ModelSettings, Settings, load_settings
from market_events.model_client import BudgetExceeded, ModelClient, ModelError
from market_events.schemas import FilterDecision
from test_routing import article

ROOT = Path(__file__).resolve().parents[1]


class Response:
    status_code = 200

    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self.content


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def post(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return Response(result)


def settings(**kwargs):
    return Settings(
        root=ROOT,
        mode="live",
        slm=ModelSettings(model="small"),
        llm=ModelSettings(model="large"),
        max_tokens=100000,
        **kwargs,
    )


def decision():
    return {
        "relevance": "relevant",
        "event_type": "earnings",
        "reason": "facts",
        "source_spans": [article().text],
    }


def test_unknown_usage_stays_unknown():
    session = Session([{"message": {"content": json.dumps(decision())}}])
    client = ModelClient(settings(), "run", session)
    client.ask("filter", article(), FilterDecision, role="slm")
    assert client.calls[0].input_tokens is None
    assert client.calls[0].output_tokens is None
    assert session.requests[0][1]["json"]["stream"] is False


def test_sarvam_v1_uses_the_task_schema_without_reasoning():
    config = settings()
    config.slm = ModelSettings(
        provider="openai_compatible",
        base_url="https://api.sarvam.ai/v1",
        model="sarvam-105b-conversations",
        api_key="test-key",
    )
    session = Session([{"choices": [{"message": {"content": json.dumps(decision())}}]}])
    client = ModelClient(config, "run", session)
    client.ask("filter", article(), FilterDecision, role="slm")

    args, request = session.requests[0]
    assert args == ("https://api.sarvam.ai/v1/chat/completions",)
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"]["reasoning_effort"] is None
    assert request["json"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "FilterDecision",
            "schema": FilterDecision.model_json_schema(),
            "strict": True,
        },
    }


def test_sarvam_environment_key_is_shared_only_at_the_sarvam_endpoint(monkeypatch, tmp_path):
    for role in ("SLM", "LLM"):
        for field in ("PROVIDER", "BASE_URL", "MODEL", "API_KEY"):
            monkeypatch.delenv(f"{role}_{field}", raising=False)
    monkeypatch.setenv("SARVAM_API_KEY", "test-sarvam-key")
    config = load_settings(tmp_path)
    assert config.slm.model == "sarvam-105b-conversations"
    assert config.llm.model == "sarvam-105b"
    for model in (config.slm, config.llm):
        assert model.base_url == "https://api.sarvam.ai/v1"
        assert model.api_key.get_secret_value() == "test-sarvam-key"

    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://another.example/v1")
    monkeypatch.setenv("LLM_MODEL", "another-model")
    other = load_settings(tmp_path).llm
    assert other.model == "another-model"
    assert not other.api_key.get_secret_value()


def test_malformed_and_transient_calls_logged_with_bounded_retry():
    session = Session(
        [
            requests.Timeout(),
            {
                "message": {"content": json.dumps(decision())},
                "prompt_eval_count": 42,
                "eval_count": 9,
            },
        ]
    )
    client = ModelClient(settings(), "r", session)
    client.ask("filter", article(), FilterDecision)
    assert [c.status for c in client.calls] == ["failed", "success"]
    assert client.calls[-1].input_tokens == 42
    assert client.calls[-1].retries == 1
    client = ModelClient(settings(), "r", Session([{"message": {"content": "bad"}}] * 2))
    with pytest.raises(ModelError):
        client.ask("filter", article(), FilterDecision)
    assert len(client.calls) == 2


def test_request_and_token_admission_limits():
    client = ModelClient(settings(max_requests=1), "r", Session([requests.Timeout()]))
    with pytest.raises(BudgetExceeded):
        client.ask("filter", article(), FilterDecision)
    assert len(client.calls) == 1
    config = settings()
    config.max_tokens = 256
    client = ModelClient(config, "r", Session([]))
    with pytest.raises(BudgetExceeded):
        client.ask("filter", article(), FilterDecision)
    assert not client.calls


def test_snapshot_never_contains_api_keys():
    config = settings()
    config.llm.api_key = "secret"
    assert "api_key" not in config.snapshot()["llm"]


def test_prompt_bound_schemas_carry_no_docstring_descriptions():
    """These schemas are embedded in live prompts and hashed into request_hash.

    A class docstring would become a schema "description" and silently change every
    live model request, so documentation for them must stay in comments.
    """
    from market_events.agents.explanation_agent import Explanation
    from market_events.schemas import EventExtraction, ExtractedAmount

    for model in (FilterDecision, EventExtraction, ExtractedAmount, Explanation):
        assert model.__doc__ is None, model.__name__
        schema = json.dumps(model.model_json_schema())
        assert '"description"' not in schema, model.__name__
