"""Comparisons must not manufacture measurement or revise original decisions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_events.experiments import (
    AGREEMENT_LABEL,
    compare_ablations,
    estimated_cost,
    extraction_agreement,
    matched_policy_inputs,
    run_experiments,
    summarize_policies,
)
from market_events.fusion import assess_evidence
from market_events.schemas import (
    AnalysisRun,
    Assessment,
    EventExtraction,
    ExposureMatch,
    EventOutcome,
    FilterDecision,
    MarketFeatures,
    ModelCall,
)

NOW = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


def make_run(identifier="run", mode="replay", policy="llm_only"):
    return AnalysisRun(
        run_id=identifier,
        article_id="article",
        policy=policy,
        decision_time=NOW,
        status="completed",
        created_at=NOW,
        config_snapshot={},
        mode=mode,
    )


def test_replay_and_live_usage_are_separate_and_unknown_is_not_zero():
    replay = make_run()
    live = make_run("live", "live")
    live.calls = [
        ModelCall(
            trace_id="t",
            run_id="live",
            task="extract",
            provider="test",
            model="test",
            prompt_version="v1",
            latency_ms=12,
            status="success",
            mode="live",
            input_tokens=20,
        )
    ]
    rows = summarize_policies([replay, live])
    assert len(rows) == 2
    assert all(row["input_tokens"] is None for row in rows)
    assert all(row["usage_complete"] is False for row in rows)


def test_cohorts_require_same_mode_article_and_cutoff():
    runs = [make_run(policy=p) for p in ("llm_only", "slm_filter", "slm_delegate")]
    runs.append(make_run("other", "live"))
    cohorts = matched_policy_inputs(runs)
    assert sum(c["all_three_policies"] for c in cohorts) == 1
    assert len(cohorts) == 2


def test_ablation_preserves_missing_commodity_gate_and_original_run():
    run = make_run()
    run.extraction = EventExtraction(
        event_id="e",
        event_type="commodity_supply_disruption",
        company_id="stock",
        commodity_id="oil",
        validation_status="validated",
        source_spans=["supply"],
    )
    run.exposure = ExposureMatch(status="missing")
    run.features = MarketFeatures(
        decision_time=NOW,
        company_id="stock",
        values={"excess_return": 0.02, "commodity_return": None},
    )
    rules = {"version": "test-v1"}
    run.assessment = assess_evidence(run.extraction, run.exposure, run.features, rules)
    run.config_snapshot = {
        "fusion_rules.json": {"version": "contract-snapshot"},
        "fusion_rules": {"version": "legacy"},
    }
    before = run.model_dump_json()
    rows = compare_ablations([run])
    assert rows[0]["direction"] == "positive"
    assert rows[1]["direction"] == "abstain"
    assert rows[1]["abstention_reasons"]
    assert {row["rules_version"] for row in rows} == {"contract-snapshot"}
    assert run.model_dump_json() == before


def test_missing_inputs_are_unavailable_not_an_invented_score():
    row = compare_ablations([make_run()])[0]
    assert row["status"] == "unavailable"
    assert "evidence_score" not in row


def test_explanation_usage_is_separate_and_outcomes_keep_mode_provenance():
    analysis = make_run("analysis", "replay")
    child = make_run("child", "live", "slm_delegate")
    child.status = "explanation_completed"
    child.parent_run_id = analysis.run_id
    child.config_snapshot = {"explanation_parent_run_id": analysis.run_id}
    storage = SimpleNamespace(
        list_runs=lambda: [analysis, child],
        list_outcomes=lambda: [EventOutcome(run_id=analysis.run_id, status="pending")],
    )
    report = run_experiments(SimpleNamespace(storage=storage))
    assert [row["mode"] for row in report["policy_summary"]] == ["replay"]
    assert [row["mode"] for row in report["explanation_summary"]] == ["live"]
    assert report["matched_inputs"][0]["policies"] == ["llm_only"]
    assert [row["run_id"] for row in report["ablations"]] == ["analysis"]
    assert report["run_manifest"][1]["run_kind"] == "explanation"
    assert report["outcomes"][0]["mode"] == "replay"
    assert report["outcomes"][0]["status"] == "pending"


def test_cohorts_expose_configuration_changes_and_keep_explicit_repeats():
    runs = [make_run(str(i), policy=p) for i, p in enumerate(("llm_only", "slm_filter"))]
    for run in runs:
        run.config_snapshot = {"fusion_rules.json": {"version": "v1"}, "root": run.run_id}
    repeated = runs[0].model_copy(deep=True, update={"run_id": "repeat", "parent_run_id": "0"})
    runs.append(repeated)
    cohort = matched_policy_inputs(runs)[0]
    assert cohort["same_saved_configuration"] is True
    assert cohort["configuration_variants"] == 1
    assert len(cohort["run_ids"]) == 3
    runs[1].config_snapshot["fusion_rules.json"]["version"] = "v2"
    assert matched_policy_inputs(runs)[0]["same_saved_configuration"] is False
    assert matched_policy_inputs([make_run()])[0]["same_saved_configuration"] is False


def test_mismatched_replay_calls_are_not_counted_as_measured_live_usage():
    run = make_run(mode="live")
    run.calls = [
        ModelCall(
            trace_id="t",
            run_id=run.run_id,
            task="filter",
            provider="test",
            model="test",
            prompt_version="v1",
            latency_ms=1,
            status="success",
            mode="replay",
            input_tokens=20,
            output_tokens=10,
        )
    ]
    row = summarize_policies([run])[0]
    assert row["mismatched_mode_calls"] == 1
    assert row["usage_complete"] is False
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None


def test_bad_snapshot_and_unresolved_source_history_remain_unavailable():
    run = make_run()
    run.extraction = EventExtraction(
        event_id="e", event_type="earnings", company_id="stock", validation_status="validated"
    )
    run.exposure = ExposureMatch(status="not_required")
    run.features = MarketFeatures(
        decision_time=NOW, company_id="stock", values={"excess_return": 0.02}
    )
    run.config_snapshot = {"fusion_rules.json": {"version": ""}}
    before = run.model_dump_json()
    assert compare_ablations([run])[0]["status"] == "unavailable"
    assert run.model_dump_json() == before
    run.config_snapshot = {"fusion_rules.json": {"version": "v1"}}
    run.memory = {"status": "unresolved"}
    row = compare_ablations([run])[0]
    assert row["status"] == "unavailable"
    assert "unresolved" in row["reason"]


PRICES = {
    "currency": "USD",
    "models": [{"provider": "test", "model": "m", "input_per_1k": 0.5, "output_per_1k": 2.0}],
}
ROOT = Path(__file__).resolve().parents[1]


def call(mode="live", input_tokens=1000, output_tokens=500, model="m"):
    return ModelCall(
        trace_id="t",
        run_id="r",
        task="filter",
        provider="test",
        model=model,
        prompt_version="v1",
        latency_ms=1,
        status="success",
        mode=mode,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def test_estimated_cost_only_for_complete_priced_live_usage():
    assert estimated_cost("live", [call(), call()], PRICES) == pytest.approx(2 * (0.5 + 1.0))
    assert estimated_cost("live", [call(), call(output_tokens=None)], PRICES) is None
    assert estimated_cost("live", [call(model="unpriced")], PRICES) is None
    assert estimated_cost("replay", [call(mode="replay")], PRICES) is None
    assert estimated_cost("live", [call()], None) is None
    assert estimated_cost("live", [call()], {"models": []}) is None
    assert estimated_cost("live", [], PRICES) is None
    live = make_run("live", "live")
    live.calls = [call()]
    row = summarize_policies([live], PRICES)[0]
    assert row["estimated_cost"] == pytest.approx(1.5) and row["cost_currency"] == "USD"
    incomplete = make_run("partial", "live")
    incomplete.calls = [call(input_tokens=None)]
    row = summarize_policies([incomplete], PRICES)[0]
    assert row["estimated_cost"] is None and row["cost_currency"] is None
    assert row["input_tokens"] is None  # never filled in


def test_bundled_price_config_has_no_invented_rates():
    config = json.loads((ROOT / "configs/model_prices.json").read_text(encoding="utf-8"))
    assert config["models"] == []


def labelled_run(identifier, article_id, relevance, event_type=None, direction=None):
    run = make_run(identifier, policy="slm_delegate")
    run.article_id = article_id
    run.filter_decision = FilterDecision(
        relevance=relevance, event_type=event_type or "other", reason="fixture"
    )
    if relevance != "irrelevant":
        run.extraction = EventExtraction(
            event_id="e",
            event_type=event_type or "other",
            company_id="NSE:A",
            validation_status="validated" if event_type == "earnings" else "unresolved",
        )
        run.assessment = Assessment(
            direction=direction or "positive",
            coverage=1,
            rules_version="v1",
            explanation="x",
            abstention_reasons=["Unsupported event family"] if direction == "abstain" else [],
        )
    return run


def gold_label(relevance, event_type):
    return {
        "relevance": relevance,
        "event_type": event_type,
        "company_id": "NSE:A",
        "commodity_id": None,
    }


def test_extraction_agreement_counts_uncertain_as_forwarded_and_is_read_only():
    gold = {
        "version": "g1",
        "labels": {
            "a": gold_label("relevant", "earnings"),
            "b": gold_label("irrelevant", "other"),
            "c": gold_label("irrelevant", "other"),
            "d": gold_label("relevant", "earnings"),
        },
    }
    runs = [
        labelled_run("1", "a", "relevant", "earnings"),
        labelled_run("2", "b", "uncertain", "uncertain", "abstain"),
        labelled_run("3", "c", "irrelevant"),
        labelled_run("4", "d", "irrelevant"),
        labelled_run("5", "unlabelled", "relevant", "earnings"),
    ]
    before = [run.model_dump_json() for run in runs]
    report = extraction_agreement(runs, gold)
    assert [run.model_dump_json() for run in runs] == before
    assert report["label"] == AGREEMENT_LABEL and "not a benchmark" in report["label"]
    assert report["unlabelled_runs"] == 1
    (row,) = report["groups"]
    assert row["filter_confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert row["filter_recall"] == 0.5 and row["filter_precision"] == 0.5
    assert row["uncertain_rate"] == 0.25
    assert row["field_accuracy"]["event_type"] == 0.5
    assert row["validation_status_rates"]["validated"] == 0.5
    assert row["abstention_rate"] == 0.5
    assert row["abstention_reasons"] == {"Unsupported event family": 1}
    assert extraction_agreement([runs[-1]], gold) is None
    assert extraction_agreement(runs, None) is None


def test_bundled_gold_labels_cover_every_synthetic_article():
    gold = json.loads((ROOT / "tests/fixtures/gold_labels.json").read_text(encoding="utf-8"))
    articles = [
        json.loads(line)
        for line in (ROOT / "tests/fixtures/articles.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert set(gold["labels"]) == {a["article_id"] for a in articles}
    assert "not a benchmark" in gold["provenance"]
    assert {label["relevance"] for label in gold["labels"].values()} == {"relevant", "irrelevant"}
