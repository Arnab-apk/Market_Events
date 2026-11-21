"""Plain-English display fields are derived from saved inputs and never persisted."""

from datetime import datetime, timezone

import pytest

from market_events.plain_language import describe_run, plain_reason, score_formula
from market_events.schemas import AnalysisRun, Assessment, EventExtraction

NOW = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)
RULE = {
    "company_id": "NSE:BERGEPAINT",
    "commodity_id": "MCX:CRUDEOIL",
    "direction": -1,
    "source": "Synthetic demonstration reviewed assumption, not a real filing",
}


def run(
    direction,
    components,
    values,
    conflicts=(),
    reasons=(),
    event="commodity_supply_disruption",
    source=None,
):
    weights = (
        {"equity": 0.6, "commodity": 0.4}
        if "commodity" in components or event == "commodity_supply_disruption"
        else {"equity": 1.0}
    )
    valid = sum(weights[k] for k in components)
    score = sum(weights[k] * v for k, v in components.items()) / valid if components else None
    rule = {**RULE, **({"source": source} if source else {})}
    return AnalysisRun(
        run_id="r",
        article_id="a",
        policy="slm_delegate",
        decision_time=NOW,
        status="abstained" if direction == "abstain" else "completed",
        created_at=NOW,
        config_snapshot={
            "companies.json": [{"instrument_id": "NSE:BERGEPAINT", "name": "Berger Paints"}]
        },
        mode="replay",
        extraction=EventExtraction(
            event_id="e",
            event_type=event,
            company_id="NSE:BERGEPAINT",
            commodity_id="MCX:CRUDEOIL",
            validation_status="validated",
        ),
        assessment=Assessment(
            direction=direction,
            evidence_score=score,
            coverage=valid / sum(weights.values()),
            conflicts=list(conflicts),
            abstention_reasons=list(reasons),
            rules_version="fusion-v1",
            explanation="saved text",
            inputs={
                "features": {"values": values},
                "components": components,
                "weights": weights,
                "rules": {"threshold": 0.15},
                "exposure": {"status": "matched", "rule": rule},
            },
        ),
    )


def test_mixed_crude_case_reads_like_the_presentation_story():
    conflict = "Equity and exposure-adjusted commodity evidence disagree"
    case = run(
        "neutral",
        {"commodity": -0.5, "equity": 0.4},
        {"excess_return": 0.008, "commodity_return": 0.015},
        conflicts=[conflict],
    )
    described = describe_run(case)
    assert described["plain_summary"] == (
        "After this crude oil supply disruption, Berger Paints beat its benchmark by 0.8%, but "
        "crude oil rose 1.5%, which counts against it under its reviewed synthetic exposure "
        "assumption, so the evidence is mixed (neutral)."
    )
    assert described["score_formula"] == (
        "0.6 × (+0.40 equity vs benchmark) + 0.4 × (−0.50 crude oil, exposure-adjusted)"
        " = +0.04 → neutral (threshold ±0.15)"
    )
    assert described["plain_reasons"] == [plain_reason(conflict)]


def test_agreeing_negative_case_and_non_synthetic_rule_wording():
    case = run(
        "negative",
        {"equity": -0.6, "commodity": -0.8},
        {"excess_return": -0.012, "commodity_return": 0.024},
        source="Annual report 2024, raw-material note",
    )
    summary = describe_run(case)["plain_summary"]
    assert "trailed its benchmark by 1.2%" in summary
    assert (
        ", and crude oil rose 2.4%, which counts against it under its reviewed exposure rule"
        in summary
    )
    assert summary.endswith("so the evidence leans negative.")
    assert "synthetic" not in summary


def test_abstention_leads_with_the_first_plain_reason_and_keeps_all_reasons():
    reasons = ["Missing or stale mandatory commodity return", "Coverage below configured minimum"]
    case = run("abstain", {"equity": 0.4}, {"excess_return": 0.008}, reasons=reasons)
    described = describe_run(case)
    assert described["plain_summary"].startswith("No assessment for Berger Paints: the commodity's")
    assert described["plain_reasons"] == [plain_reason(r) for r in reasons]
    assert described["score_formula"].endswith("→ withheld (abstain)")
    assert "÷ 0.6" in described["score_formula"]


def test_reason_mapping_falls_back_without_inventing_text():
    assert "benchmark" in plain_reason("Missing or stale mandatory equity excess return")
    assert plain_reason("Missing or stale mandatory relative_volume") == (
        "A required input (relative_volume) was not available at the cutoff."
    )
    assert plain_reason("Some future reason") == "Some future reason"


@pytest.mark.parametrize("status", ["irrelevant", "duplicate", "ineligible", "failed", "partial"])
def test_runs_without_assessment_get_a_status_sentence_and_no_formula(status):
    case = AnalysisRun(
        run_id="r",
        article_id="a",
        policy="llm_only",
        decision_time=NOW,
        status=status,
        created_at=NOW,
        config_snapshot={},
        mode="replay",
    )
    described = describe_run(case)
    assert described["plain_summary"]
    assert described["plain_reasons"] == [] and described["score_formula"] is None


def test_formula_is_none_without_components_and_fields_are_not_on_the_record():
    case = run("abstain", {}, {}, reasons=["Missing or stale mandatory equity excess return"])
    assert score_formula(case.assessment) is None
    assert "plain_summary" not in AnalysisRun.model_fields
