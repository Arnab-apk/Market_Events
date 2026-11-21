"""Two small HTTP adapters plus labelled fixture replay and bounded call accounting."""

import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

import requests
from pydantic import BaseModel

from .config import Settings
from .schemas import Article, ModelCall


class ModelError(RuntimeError):
    pass


class BudgetExceeded(ModelError):
    pass


class ModelClient:
    """One instance per run. Every attempted request is retained, including failures."""

    def __init__(self, settings: Settings, run_id: str, session=None):
        self.settings = settings
        self.run_id = run_id
        self.session = session or requests.Session()
        self.calls: list[ModelCall] = []
        self.reserved_tokens = 0

    def ask(
        self,
        task: str,
        article: Article,
        schema: type[BaseModel],
        role: str = "llm",
        context: dict | None = None,
    ) -> BaseModel:
        model = getattr(self.settings, role)
        prompt_name = {
            "filter": "filter_event",
            "extraction": "extract_event",
            "explanation": "explain_assessment",
        }[task]
        prompt = (self.settings.root / "prompts" / f"{prompt_name}.md").read_text(encoding="utf-8")
        prompt_version = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        payload = {
            "article_id": article.article_id,
            "published_at": article.published_at.isoformat(),
            "source_version": article.source_version,
            "text": article.text,
            "context": context or {},
        }
        messages = [
            {
                "role": "system",
                "content": prompt
                + "\nReturn a JSON object using this schema:\n"
                + json.dumps(schema.model_json_schema()),
            },
            {"role": "user", "content": json.dumps(payload)},
        ]
        request_hash = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
        # Byte count is a conservative local admission bound, not provider-reported token usage.
        reservation = len(json.dumps(messages).encode("utf-8")) + model.max_output_tokens
        for attempt in range(2):
            if len(self.calls) >= self.settings.max_requests:
                raise BudgetExceeded("Per-run request limit reached")
            if self.reserved_tokens + reservation > self.settings.max_tokens:
                raise BudgetExceeded("Per-run conservative token admission limit reached")
            self.reserved_tokens += reservation
            started = time.perf_counter()
            trace = ModelCall(
                trace_id=str(uuid4()),
                run_id=self.run_id,
                task=task,
                provider="fixture" if self.settings.mode == "replay" else model.provider,
                model=f"recorded-{role}" if self.settings.mode == "replay" else model.model,
                prompt_version=prompt_version,
                latency_ms=0,
                retries=attempt,
                status="started",
                mode=self.settings.mode,
                request_hash=request_hash,
                requested_model=model.model if self.settings.mode == "live" else None,
            )
            retryable = False
            try:
                if self.settings.mode == "replay":
                    raw = self._replay(article, task)
                else:
                    if not model.model:
                        raise ModelError(f"Set {role.upper()}_MODEL before using live mode")
                    raw, usage, actual_model = self._live(model, messages)
                    trace.input_tokens, trace.output_tokens = usage
                    trace.model = actual_model
                    if actual_model != model.model:
                        trace.compatibility_warning = "Provider returned a different model identity; review experiment compatibility"
                result = schema.model_validate(raw)
                trace.status = "success"
                if hasattr(result, "trace_id"):
                    result.trace_id = trace.trace_id
                return result
            except requests.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                retryable = code in {408, 429, 500, 502, 503, 504}
                trace.error = f"Model HTTP error {code}"
            except (requests.Timeout, requests.ConnectionError):
                retryable = True
                trace.error = "Model endpoint timed out or could not be reached"
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                retryable = self.settings.mode == "live"
                trace.error = f"Invalid structured model response ({type(exc).__name__})"
            except ModelError as exc:
                trace.error = str(exc)
            finally:
                trace.latency_ms = (time.perf_counter() - started) * 1000
                if trace.status != "success":
                    trace.status = "failed"
                self.calls.append(trace)
            if not retryable or attempt == 1:
                raise ModelError(trace.error)
        raise ModelError("Model request failed")

    def _replay(self, article, task):
        filename: Path = self.settings.root / "tests/fixtures/recorded_model_outputs.json"
        outputs = json.loads(filename.read_text(encoding="utf-8"))
        item = outputs.get(article.article_id)
        if item is None or task not in item:
            raise ModelError("No recorded replay for this article/task; configure live models")
        # Replay only the exact fixture text and version, never an unrelated uploaded article.
        from .ingestion import import_articles

        originals = import_articles(self.settings.root / "tests/fixtures/articles.jsonl").records
        original = next((a for a in originals if a.article_id == article.article_id), None)
        if (
            original is None
            or original.content_hash != article.content_hash
            or original.source_version != article.source_version
        ):
            raise ModelError("Replay source does not match the recorded fixture")
        return item[task]

    def _live(self, model, messages):
        headers = {"Content-Type": "application/json"}
        if model.api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {model.api_key.get_secret_value()}"
        if model.provider == "ollama":
            endpoint = model.base_url + "/api/chat"
            payload = {
                "model": model.model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "think": False,
                "options": {"temperature": 0, "num_predict": model.max_output_tokens},
            }
        else:
            endpoint = model.base_url + "/chat/completions"
            payload = {
                "model": model.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "max_tokens": model.max_output_tokens,
            }
        response = self.session.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if model.provider == "ollama":
            content = data["message"]["content"]
            usage = (data.get("prompt_eval_count"), data.get("eval_count"))
        else:
            content = data["choices"][0]["message"]["content"]
            usage = (
                data.get("usage", {}).get("prompt_tokens"),
                data.get("usage", {}).get("completion_tokens"),
            )
        return json.loads(content), usage, data.get("model", model.model)
