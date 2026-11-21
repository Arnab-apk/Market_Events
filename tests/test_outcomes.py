import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from market_events.outcomes import evaluate_outcome
from market_events.schemas import AnalysisRun, Assessment, EventExtraction, MarketObservation

CUTOFF = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)
NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def setup_case():
    with (Path(__file__).parent / "fixtures/market_prices.csv").open() as stream:
        rows = [
            MarketObservation.model_validate({**r, "contract_id": r["contract_id"] or None})
            for r in csv.DictReader(stream)
        ]
    run = AnalysisRun(
        run_id="r",
        article_id="syn-001",
        policy="llm_only",
        decision_time=CUTOFF,
        status="completed",
        created_at=CUTOFF,
        config_snapshot={},
        mode="replay",
        extraction=EventExtraction(
            event_id="e",
            event_type="earnings",
            company_id="NSE:ASIANPAINT",
            validation_status="validated",
        ),
        assessment=Assessment(
            direction="positive", coverage=1, rules_version="v1", explanation="x"
        ),
    )
    return run, rows


def test_fifth_session_cost_benchmark_and_immutability():
    run, rows = setup_case()
    before = run.model_dump_json()
    result = evaluate_outcome(run, rows, "NSE:NIFTY_MATERIALS", evaluation_time=NOW)
    equity = [o for o in rows if o.instrument_id == "NSE:ASIANPAINT" and o.timestamp > CUTOFF]
    assert result.status == "completed"
    assert result.entry_time == datetime(2026, 1, 13, 3, 45, tzinfo=timezone.utc)
    local_entry = result.entry_time.astimezone(ZoneInfo("Asia/Kolkata"))
    assert (local_entry.hour, local_entry.minute) == (9, 15)
    assert result.entry_time > run.decision_time
    assert result.exit_time == equity[4].timestamp
    assert result.exit_time.day == 19  # weekend is not a trading session
    assert result.gross_return == pytest.approx(equity[4].close / equity[0].open - 1)
    assert result.net_return == pytest.approx(result.gross_return - 0.001)
    assert result.excess_return == pytest.approx(result.gross_return - result.benchmark_return)
    assert run.model_dump_json() == before
    assert "exchange-calendar completeness not verified" in result.reason


def test_session_whose_open_precedes_decision_is_not_entry():
    run, rows = setup_case()
    run.decision_time = datetime(2026, 1, 13, 8, tzinfo=timezone.utc)
    result = evaluate_outcome(run, rows, evaluation_time=NOW)
    assert result.entry_time == datetime(2026, 1, 14, 3, 45, tzinfo=timezone.utc)
    assert result.exit_time == datetime(2026, 1, 20, 10, tzinfo=timezone.utc)


def test_pending_delayed_availability_and_missing_benchmark():
    run, rows = setup_case()
    early = datetime(2026, 1, 16, 12, tzinfo=timezone.utc)
    assert evaluate_outcome(run, rows, evaluation_time=early).status == "pending"
    delayed = [
        o.model_copy(update={"available_at": NOW.replace(month=3)})
        if o.timestamp.day == 13 and o.market_family == "equity"
        else o
        for o in rows
    ]
    assert evaluate_outcome(run, delayed, evaluation_time=NOW).status == "pending"
    result = evaluate_outcome(run, rows, evaluation_time=NOW)
    assert result.status == "completed"
    assert result.benchmark_return is None
    assert "benchmark unavailable" in result.reason


def test_invalid_action_abstention_and_cost():
    run, rows = setup_case()
    run.config_snapshot["corporate_actions"] = ["split"]
    assert evaluate_outcome(run, rows, evaluation_time=NOW).status == "invalid"
    run.config_snapshot = {}
    run.assessment.direction = "abstain"
    assert evaluate_outcome(run, rows, evaluation_time=NOW).status == "invalid"
    with pytest.raises(ValueError):
        evaluate_outcome(run, rows, cost_bps=-1)


def test_conflict_after_fifth_session_does_not_change_completed_horizon():
    run, rows = setup_case()
    before = evaluate_outcome(run, rows, "NSE:NIFTY_MATERIALS", evaluation_time=NOW)
    later = next(
        o for o in rows if o.instrument_id == run.extraction.company_id and o.timestamp.day == 20
    )
    conflict = later.model_copy(update={"volume": later.volume + 1})
    assert (
        evaluate_outcome(run, rows + [conflict], "NSE:NIFTY_MATERIALS", evaluation_time=NOW)
        == before
    )


def test_unavailable_conflict_cannot_change_asof_outcome():
    run, rows = setup_case()
    before = evaluate_outcome(run, rows, "NSE:NIFTY_MATERIALS", evaluation_time=NOW)
    entry = next(
        o for o in rows if o.instrument_id == run.extraction.company_id and o.timestamp.day == 13
    )
    conflict = entry.model_copy(
        update={"volume": entry.volume + 1, "available_at": NOW + timedelta(days=1)}
    )
    assert (
        evaluate_outcome(run, rows + [conflict], "NSE:NIFTY_MATERIALS", evaluation_time=NOW)
        == before
    )
    assert (
        evaluate_outcome(run, rows + [conflict], evaluation_time=NOW + timedelta(days=1)).status
        == "invalid"
    )
