"""Screener: rule ops, missing data, abstentions, ranking and cutoff safety (offline)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from market_events.schemas import (
    AnalysisRun,
    Assessment,
    EventExtraction,
    ExecutionPolicy,
    TechnicalSnapshot,
)
from market_events.screener import load_screener_rules, screen, validate_screener_rules

AS_OF = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def run(
    company, score=0.5, coverage=1.0, direction="positive", when=None, run_id=None, reasons=None
):
    """A minimal saved run with an assessment for one synthetic company."""
    when = when or AS_OF - timedelta(days=1)
    assessment = Assessment(
        direction=direction,
        evidence_score=score,
        coverage=coverage,
        abstention_reasons=reasons or [],
        rules_version="fusion-v1",
        explanation="synthetic",
    )
    return AnalysisRun(
        run_id=run_id or f"run-{company}-{when.isoformat()}",
        article_id="SYNTHETIC:article",
        policy=ExecutionPolicy.llm_only,
        decision_time=when,
        status="completed",
        created_at=when,
        config_snapshot={},
        extraction=EventExtraction(
            event_id=f"event-{company}", event_type="earnings", company_id=company
        ),
        assessment=assessment,
        mode="replay",
    )


def rules(*rule_list, rank_by="evidence_score", max_shortlist=5):
    return {
        "version": "screener-test",
        "use_latest_run_per_company": True,
        "rules": list(rule_list),
        "rank_by": rank_by,
        "max_shortlist": max_shortlist,
    }


def rule(field, op, value):
    return {"field": field, "op": op, "value": value}


A, B, C = "SYNTHETIC:NSE:AAA", "SYNTHETIC:NSE:BBB", "SYNTHETIC:NSE:CCC"


def test_default_config_file_is_valid():
    loaded = load_screener_rules(ROOT)
    assert loaded["version"] == "screener-v1"
    assert json.loads((ROOT / "configs" / "screener_rules.json").read_text())["max_shortlist"] == 5


@pytest.mark.parametrize(
    "op,limit,passing,failing",
    [
        (">=", 0.3, 0.3, 0.29),
        ("<=", 0.3, 0.3, 0.31),
        (">", 0.3, 0.31, 0.3),
        ("<", 0.3, 0.29, 0.3),
        ("==", 0.3, 0.3, 0.31),
        ("!=", 0.3, 0.31, 0.3),
        ("in", [0.3, 0.4], 0.4, 0.5),
    ],
)
def test_each_numeric_op(op, limit, passing, failing):
    result = screen(
        [run(A, score=passing), run(B, score=failing)],
        {},
        rules(rule("evidence_score", op, limit)),
        AS_OF,
    )
    by_id = {row.company_id: row for row in result.rows}
    assert by_id[A].passed is True
    assert by_id[B].passed is False
    assert result.shortlist == [A]


@pytest.mark.parametrize(
    "op,limit,passing,failing",
    [
        ("==", "positive", "positive", "negative"),
        ("!=", "negative", "positive", "negative"),
        ("in", ["positive", "neutral"], "neutral", "negative"),
    ],
)
def test_each_text_op(op, limit, passing, failing):
    result = screen(
        [run(A, direction=passing), run(B, direction=failing)],
        {},
        rules(rule("direction", op, limit)),
        AS_OF,
    )
    by_id = {row.company_id: row for row in result.rows}
    assert by_id[A].passed and not by_id[B].passed
    assert by_id[A].checks[0]["margin"] is None


def test_check_records_value_limit_and_signed_margin():
    result = screen(
        [run(A, score=0.5, coverage=0.7)],
        {A: {"rsi14": 60.0}},
        rules(rule("evidence_score", ">=", 0.15), rule("rsi14", "<=", 70)),
        AS_OF,
    )
    first, second = result.rows[0].checks
    assert first["value"] == 0.5 and first["limit"] == 0.15 and first["passed"] is True
    assert first["margin"] == pytest.approx(0.35)
    # For an upper limit, a value below the limit is a comfortable (positive) margin.
    assert second["value"] == 60.0 and second["margin"] == pytest.approx(10.0)


def test_missing_value_fails_never_passes():
    result = screen(
        [run(A), run(B)],
        {A: {"rsi14": None}},  # A has a warm-up gap; B has no technicals at all.
        rules(rule("rsi14", "<=", 70)),
        AS_OF,
    )
    assert all(not row.passed for row in result.rows)
    assert all(row.checks[0]["value"] is None for row in result.rows)
    assert result.shortlist == []


def test_stale_technical_value_counts_as_missing():
    snapshot = TechnicalSnapshot(
        decision_time=AS_OF, company_id=A, values={"rsi14": 50.0}, stale=["rsi14"]
    )
    result = screen([run(A)], {A: snapshot}, rules(rule("rsi14", "<=", 70)), AS_OF)
    assert result.rows[0].passed is False


def test_missing_evidence_score_fails():
    result = screen([run(A, score=None)], {}, rules(rule("evidence_score", ">=", 0.1)), AS_OF)
    assert result.rows[0].passed is False


def test_abstained_assessment_always_fails_with_reason():
    abstained = run(A, score=0.9, direction="abstain", reasons=["Coverage below minimum"])
    result = screen([abstained], {}, rules(rule("evidence_score", ">=", 0.1)), AS_OF)
    row = result.rows[0]
    assert row.passed is False and row.rank is None
    assert any(check["rule"] == "abstained: Coverage below minimum" for check in row.checks)


def test_ranking_descending_with_company_tie_break_and_max_shortlist():
    result = screen(
        [run(C, score=0.4), run(B, score=0.6), run(A, score=0.6)],
        {},
        rules(rule("evidence_score", ">=", 0.1), max_shortlist=2),
        AS_OF,
    )
    ranked = sorted((row for row in result.rows if row.passed), key=lambda row: row.rank)
    assert [row.company_id for row in ranked] == [A, B, C]
    assert [row.rank for row in ranked] == [1, 2, 3]
    assert result.shortlist == [A, B]
    assert result.rows[0].score == 0.6


def test_latest_run_per_company_and_later_run_ignored():
    older = run(A, score=0.2, when=AS_OF - timedelta(days=3), run_id="old")
    newer = run(A, score=0.5, when=AS_OF - timedelta(hours=1), run_id="new")
    future = run(
        A, score=-0.9, direction="negative", when=AS_OF + timedelta(minutes=1), run_id="future"
    )
    result = screen([older, future, newer], {}, rules(rule("direction", "==", "positive")), AS_OF)
    assert len(result.rows) == 1
    assert result.rows[0].run_id == "new" and result.rows[0].passed


def test_only_future_runs_gives_empty_result():
    future = run(A, when=AS_OF + timedelta(days=1))
    result = screen([future], {}, rules(rule("evidence_score", ">=", 0.1)), AS_OF)
    assert result.rows == [] and result.shortlist == []


def test_all_runs_mode_keeps_every_eligible_run_but_unique_shortlist():
    config = rules(rule("evidence_score", ">=", 0.1))
    config["use_latest_run_per_company"] = False
    result = screen(
        [run(A, score=0.3, run_id="a1"), run(A, score=0.4, run_id="a2", when=AS_OF)],
        {},
        config,
        AS_OF,
    )
    assert len(result.rows) == 2 and result.shortlist == [A]


def test_runs_without_assessment_or_company_are_skipped():
    no_assessment = run(A).model_copy(update={"assessment": None})
    no_company = run(B).model_copy(update={"extraction": None})
    result = screen([no_assessment, no_company], {}, rules(rule("coverage", ">=", 0)), AS_OF)
    assert result.rows == []


def test_naive_as_of_rejected():
    with pytest.raises(ValueError):
        screen([], {}, rules(rule("coverage", ">=", 0)), datetime(2026, 3, 2))


@pytest.mark.parametrize(
    "bad",
    [
        rules(rule("not_a_field", ">=", 1)),
        rules(rule("coverage", "=>", 1)),
        rules(rule("coverage", ">=", "high")),
        rules(rule("coverage", ">=", float("nan"))),
        rules(rule("coverage", "in", 0.5)),
        rules(rule("coverage", ">=", 0.5), rank_by="direction"),
        rules(rule("coverage", ">=", 0.5), max_shortlist=0),
        rules(),
        {**rules(rule("coverage", ">=", 0.5)), "version": " "},
        {**rules(rule("coverage", ">=", 0.5)), "surprise": 1},
    ],
)
def test_invalid_rules_raise(bad):
    with pytest.raises(ValueError):
        validate_screener_rules(bad)
    with pytest.raises(ValueError):
        screen([run(A)], {}, bad, AS_OF)
