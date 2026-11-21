"""Run a small, labelled synthetic grounding pilot on configured local models.

This measures fixture recall and protocol reliability, not predictive performance.
Usage: .venv/Scripts/python.exe scripts/benchmark_models.py --limit 30
"""

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from market_events.agents.event_agent import extract_event
from market_events.agents.filter_agent import filter_article
from market_events.config import load_settings, read_config
from market_events.ingestion import import_articles
from market_events.model_client import ModelClient, ModelError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--extractions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("runs/local_model_pilot.json"))
    args = parser.parse_args()
    settings = load_settings()
    settings.mode = "live"
    settings.max_tokens = 30000
    settings.timeout_seconds = 180
    articles = import_articles(settings.root / "tests/fixtures/articles.jsonl").records[
        : args.limit
    ]
    expected = json.loads(
        (settings.root / "tests/fixtures/recorded_model_outputs.json").read_text(encoding="utf-8")
    )
    companies = read_config(settings.root, "companies.json")
    report = {
        "provenance": "Actual local inference on authored synthetic fixtures. Not a real-data or held-out model benchmark.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings.snapshot(),
        "filter_items": [],
        "extraction_items": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for article in articles:
        client = ModelClient(settings, str(uuid4()))
        item = {
            "article_id": article.article_id,
            "expected": expected[article.article_id]["filter"]["relevance"],
        }
        try:
            result = filter_article(article, client, context={"companies": companies})
            item["result"] = result.model_dump(mode="json")
        except ModelError as exc:
            item["error"] = str(exc)
        item["calls"] = [c.model_dump(mode="json") for c in client.calls]
        report["filter_items"].append(item)
        save()
        print(
            f"filter {article.article_id}: {item.get('result', {}).get('relevance', item.get('error'))}",
            flush=True,
        )
    selected, families = [], set()
    for article in articles:
        family = expected[article.article_id].get("extraction", {}).get("event_type")
        if (
            family in {"earnings", "order_announcement", "commodity_supply_disruption"}
            and family not in families
        ):
            selected.append(article)
            families.add(family)
    for article in selected[: args.extractions]:
        client = ModelClient(settings, str(uuid4()))
        item = {"article_id": article.article_id}
        try:
            result = extract_event(article, client, companies)
            item["result"] = result.model_dump(mode="json")
        except ModelError as exc:
            item["error"] = str(exc)
        item["calls"] = [c.model_dump(mode="json") for c in client.calls]
        report["extraction_items"].append(item)
        save()
        print(
            f"extraction {article.article_id}: {item.get('result', {}).get('validation_status', item.get('error'))}",
            flush=True,
        )
    positives = [i for i in report["filter_items"] if i["expected"] != "irrelevant"]
    forwarded = sum(
        i.get("result", {}).get("relevance") in {"relevant", "uncertain"} for i in positives
    )
    latencies = [c["latency_ms"] for i in report["filter_items"] for c in i["calls"]]
    report["summary"] = {
        "filter_items": len(articles),
        "filter_failures": sum("error" in i for i in report["filter_items"]),
        "relevant_or_uncertain_expected": len(positives),
        "forwarded": forwarded,
        "fixture_forward_recall": forwarded / len(positives) if positives else None,
        "filter_median_call_latency_ms": statistics.median(latencies) if latencies else None,
        "validated_extractions": sum(
            i.get("result", {}).get("validation_status") == "validated"
            for i in report["extraction_items"]
        ),
        "extraction_items": len(report["extraction_items"]),
        "resource_use": "Not instrumented; cold/warm calls mixed and reported in sequence, no latency superiority claim.",
    }
    save()
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
