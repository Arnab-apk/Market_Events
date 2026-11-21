"""Synthetic numerical examples only; no financial feeds or provider calls."""

from datetime import datetime, timedelta, timezone
from math import sqrt

import pytest

from market_events.schemas import MarketObservation
from market_events.technicals import compute_technicals

COMPANY = "NSE:SYNTHETIC"
START = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
HISTORY = {
    "rsi14": 15,
    "sma20": 20,
    "sma50": 50,
    "ema20": 20,
    "macd_line": 26,
    "macd_signal": 34,
    "macd_histogram": 34,
    "bollinger20_middle": 20,
    "bollinger20_upper": 20,
    "bollinger20_lower": 20,
    "atr14": 15,
    "adx14": 28,
}


def bars(closes, spread=1):
    """Synthetic observed dates; intentionally no exchange-calendar assertion."""
    return [
        MarketObservation(
            instrument_id=COMPANY,
            market_family="equity",
            timestamp=START + timedelta(days=index),
            available_at=START + timedelta(days=index, minutes=5),
            open=close,
            high=close + spread,
            low=close - spread,
            close=close,
            volume=1000,
            currency="INR",
            unit="share",
        )
        for index, close in enumerate(closes)
    ]


def snapshot(rows, cutoff=None):
    return compute_technicals(rows, cutoff or max(row.available_at for row in rows), COMPANY)


def test_monotone_worked_example_and_input_immutability():
    rows = bars(range(100, 160))
    original = [row.model_dump_json() for row in rows]
    result = snapshot(rows)
    assert result.values == pytest.approx(
        {
            "rsi14": 100,
            "sma20": 149.5,
            "sma50": 134.5,
            "ema20": 149.5,
            "macd_line": 7,
            "macd_signal": 7,
            "macd_histogram": 0,
            "bollinger20_middle": 149.5,
            "bollinger20_upper": 149.5 + sqrt(133),
            "bollinger20_lower": 149.5 - sqrt(133),
            "atr14": 2,
            "adx14": 100,
        }
    )
    assert result.missing == result.stale == []
    assert result.history_bars == 60
    assert result.required_history == HISTORY
    assert set(result.observation_ids) == {row.observation_id for row in rows}
    assert result.definition_version == "technicals-v1"
    assert snapshot(list(reversed(rows))) == result
    assert [row.model_dump_json() for row in rows] == original
    assert "not buy/sell advice" in result.interpretation["context"]


def test_declining_closes_have_zero_rsi_and_directionless_adx():
    result = snapshot(bars(range(200, 140, -1)))
    assert result.values["rsi14"] == 0
    assert result.values["adx14"] == pytest.approx(100)
    assert result.values["macd_line"] == pytest.approx(-7)
    assert "not trend direction" in result.interpretation["adx14"]


@pytest.mark.parametrize("spread, expected_atr", [(0, 0), (2, 4)])
def test_constant_prices_have_defined_flat_edges(spread, expected_atr):
    result = snapshot(bars([100] * 60, spread))
    assert result.values["rsi14"] == 50
    assert result.values["atr14"] == expected_atr
    assert result.values["adx14"] == 0
    assert result.values["macd_line"] == result.values["macd_signal"] == 0
    assert result.values["macd_histogram"] == 0
    assert all(
        result.values[key] == 100
        for key in (
            "sma20",
            "sma50",
            "ema20",
            "bollinger20_middle",
            "bollinger20_upper",
            "bollinger20_lower",
        )
    )
    assert not result.missing


def test_mixed_gain_loss_rsi_seed_and_wilder_updates():
    closes = [100]
    for change in [2, -1] * 7:
        closes.append(closes[-1] + change)
    assert snapshot(bars(closes)).values["rsi14"] == pytest.approx(100 * 2 / 3)
    closes.append(closes[-1] + 3)
    assert snapshot(bars(closes)).values["rsi14"] == pytest.approx(100 * 32 / 45)
    closes.append(closes[-1] - 4)
    assert snapshot(bars(closes)).values["rsi14"] == pytest.approx(100 * 416 / 697)


def test_atr_excludes_initial_range_and_includes_gap_then_wilder_update():
    rows = bars([100] * 15)
    rows[0] = rows[0].model_copy(update={"high": 150, "low": 50})
    assert snapshot(rows).values["atr14"] == pytest.approx(2)
    gap = bars([100] * 15 + [110])[-1]
    # Range=2 but gap true range=11, so the ATR update is (13*2 + 11)/14.
    assert snapshot(rows + [gap]).values["atr14"] == pytest.approx(37 / 14)


def test_adx_seed_and_direction_reversal_wilder_update():
    rows = bars(list(range(100, 128)) + [126])
    assert snapshot(rows[:28]).values["adx14"] == pytest.approx(100)
    # First down step: smoothed +DM=13/14, -DM=1/14, DX=600/7.
    # ADX29=(13*100 + 600/7)/14 = 4850/49.
    assert snapshot(rows).values["adx14"] == pytest.approx(4850 / 49)


def test_tied_directional_moves_are_both_zero():
    rows = bars([100] * 28, spread=0)
    rows = [
        row.model_copy(update={"high": 100 + index, "low": 100 - index})
        for index, row in enumerate(rows)
    ]
    assert snapshot(rows).values["adx14"] == 0
    assert snapshot(rows).values["atr14"] > 0


def test_ema_seed_and_macd_signal_known_shock_example():
    assert snapshot(bars([100] * 20 + [121])).values["ema20"] == pytest.approx(102)
    rows = bars([100] * 26 + [110] * 8)
    result = snapshot(rows)
    fast_ratio, slow_ratio = 11 / 13, 25 / 27
    expected_line = 10 * (slow_ratio**8 - fast_ratio**8)
    expected_signal = (
        10 / 9 * ((1 - slow_ratio**9) / (1 - slow_ratio) - (1 - fast_ratio**9) / (1 - fast_ratio))
    )
    assert result.values["macd_line"] == pytest.approx(expected_line)
    assert result.values["macd_signal"] == pytest.approx(expected_signal)
    assert result.values["macd_histogram"] == pytest.approx(expected_line - expected_signal)
    updated = snapshot(bars([100] * 26 + [110] * 8 + [90]))
    fast = 110 - 10 * fast_ratio**8
    slow = 110 - 10 * slow_ratio**8
    next_line = fast + (90 - fast) * 2 / 13 - slow - (90 - slow) * 2 / 27
    assert updated.values["macd_line"] == pytest.approx(next_line)
    assert updated.values["macd_signal"] == pytest.approx(0.8 * expected_signal + 0.2 * next_line)


@pytest.mark.parametrize("count", [0, 1, 14, 15, 19, 20, 25, 26, 27, 28, 33, 34, 49, 50])
def test_exact_minimum_histories_and_no_zero_warmup_filling(count):
    rows = bars(range(100, 100 + count))
    cutoff = rows[-1].available_at if rows else START
    result = compute_technicals(rows, cutoff, COMPANY)
    expected_missing = {key for key, minimum in HISTORY.items() if count < minimum}
    assert set(result.values) == set(HISTORY)
    assert set(result.missing) == expected_missing
    assert result.required_history == HISTORY
    assert result.history_bars == count
    for key in expected_missing:
        assert result.values[key] is None
        assert f"requires {HISTORY[key]}" in result.interpretation[key]
    for key in set(HISTORY) - expected_missing:
        assert result.values[key] is not None


def test_timestamp_and_availability_boundaries_with_future_conflicts():
    rows = bars(range(100, 161))
    cutoff = rows[59].available_at
    baseline = snapshot(rows[:60], cutoff)
    delayed = rows[59].model_copy(update={"available_at": cutoff + timedelta(seconds=1)})
    altered = rows[59].model_copy(
        update={"volume": 1234, "available_at": cutoff + timedelta(days=1)}
    )
    assert snapshot(rows + [altered], cutoff) == baseline
    result = snapshot(rows[:59] + [delayed, rows[60]], cutoff)
    assert result == snapshot(rows[:59], cutoff)
    exact_timestamp = rows[59].model_copy(update={"available_at": rows[59].timestamp})
    assert snapshot(rows[:59] + [exact_timestamp], rows[59].timestamp).history_bars == 60
    assert all(
        row.timestamp <= cutoff and row.available_at <= cutoff
        for row in rows
        if row.observation_id in baseline.observation_ids
    )


@pytest.mark.parametrize("kind", ["duplicate", "same_session", "currency", "unit", "contract_id"])
def test_ambiguous_eligible_history_is_not_computed(kind):
    rows = bars(range(100, 160))
    if kind == "duplicate":
        rows.append(rows[-1].model_copy(update={"volume": 1234}))
    elif kind == "same_session":
        rows.append(
            MarketObservation.model_validate(
                {
                    **rows[-1].model_dump(exclude={"observation_id"}),
                    "timestamp": rows[-1].timestamp + timedelta(minutes=1),
                }
            )
        )
    else:
        rows[0] = rows[0].model_copy(update={kind: "different"})
    result = snapshot(rows)
    assert all(value is None for value in result.values.values())
    assert set(result.missing) == set(HISTORY)
    assert not result.stale
    assert all("withheld" in result.interpretation[key] for key in HISTORY)


def test_exact_duplicates_and_unrelated_series_do_not_change_snapshot():
    rows = bars(range(100, 160))
    other_equity = MarketObservation.model_validate(
        {
            **rows[-1].model_dump(exclude={"observation_id"}),
            "instrument_id": "NSE:OTHER",
        }
    )
    benchmark = rows[-1].model_copy(update={"market_family": "benchmark", "unit": "index"})
    assert snapshot(rows + [rows[-1].model_copy(), other_equity, benchmark]) == snapshot(rows)


def test_four_calendar_day_stale_boundary_withholds_interpretation():
    rows = bars(range(100, 160))
    boundary = rows[-1].timestamp + timedelta(days=4)
    fresh = snapshot(rows, boundary)
    stale = snapshot(rows, boundary + timedelta(microseconds=1))
    assert not fresh.stale
    assert stale.values == fresh.values
    assert set(stale.stale) == set(HISTORY)
    assert all("Stale:" in stale.interpretation[key] for key in HISTORY)


def test_cutoff_timezone_normalization_and_request_validation():
    rows = bars(range(100, 160))
    india = timezone(timedelta(hours=5, minutes=30))
    assert snapshot(rows, rows[-1].available_at.astimezone(india)) == snapshot(rows)
    with pytest.raises(ValueError, match="timezone"):
        snapshot(rows, rows[-1].available_at.replace(tzinfo=None))
    with pytest.raises(ValueError, match="company_id"):
        compute_technicals(rows, rows[-1].available_at, " ")
