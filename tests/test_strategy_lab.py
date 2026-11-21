"""Offline numerical, accounting and future-perturbation research checks."""

import json
import random
from datetime import date, datetime, timedelta, timezone
from math import cos, sin, sqrt
from statistics import fmean, stdev

import numpy as np
import pytest

from market_events.schemas import MarketObservation
from market_events.strategy_lab import (
    indicator_series,
    monte_carlo,
    prepare_history,
    probabilistic_sharpe,
    run_backtest,
    walk_forward,
)
from market_events.technicals import compute_technicals

COMPANY = "NSE:SYNTHETIC"
START = datetime(2019, 1, 1, 10, tzinfo=timezone.utc)
MINIMUMS = {
    "sma20": 20,
    "sma50": 50,
    "sma200": 200,
    "ema20": 20,
    "ema50": 50,
    "rsi14": 15,
    "macd_line": 26,
    "macd_signal": 34,
    "macd_histogram": 34,
    "bollinger20_middle": 20,
    "bollinger20_upper": 20,
    "bollinger20_lower": 20,
    "atr14": 15,
    "adx14": 28,
}
STRATEGIES = (
    "buy_hold",
    "sma_cross",
    "ema_cross",
    "rsi_reversion",
    "macd_cross",
    "bollinger_reversion",
)


def bars(closes, opens=None, spread=1):
    opens = list(closes) if opens is None else opens
    return [
        MarketObservation(
            instrument_id=COMPANY,
            market_family="equity",
            timestamp=START + timedelta(days=i),
            available_at=START + timedelta(days=i, minutes=5),
            open=opening,
            high=max(opening, close) + spread,
            low=min(opening, close) - spread,
            close=close,
            volume=1000,
            currency="INR",
            unit="share",
        )
        for i, (opening, close) in enumerate(zip(opens, closes))
    ]


def replace(row, **changes):
    # Reset natural-key identity when changing instrument/date/contract.
    payload = row.model_dump(exclude={"observation_id"})
    return MarketObservation.model_validate({**payload, **changes})


def prepare(rows, **kwargs):
    return prepare_history(rows, COMPANY, date(2019, 1, 1), date(2020, 12, 31), **kwargs)


def wave(count=260):
    closes = [150 + 24 * sin(i / 6) + 7 * cos(i / 2.7) + i / 30 for i in range(count)]
    opens = [close + 3 * sin(i / 3.1) for i, close in enumerate(closes)]
    return bars(closes, opens)


def test_history_sort_deduplicate_filter_without_mutation_or_backdated_availability():
    rows = bars([100, 101, 102])
    rows = [replace(r, available_at=datetime(2026, 10, 26, tzinfo=timezone.utc)) for r in rows]
    original = [r.model_dump_json() for r in rows]
    unrelated = replace(rows[0], instrument_id="NSE:OTHER", currency="USD")
    benchmark = replace(rows[0], market_family="benchmark")
    result = prepare(list(reversed(rows)) + [rows[0], unrelated, benchmark])
    assert result == rows
    assert [r.model_dump_json() for r in rows] == original
    assert result[0].available_at.year == 2026
    with pytest.raises(ValueError, match="No eligible"):
        prepare(rows, as_of=datetime(2020, 12, 31, tzinfo=timezone.utc))


def test_history_cutoff_filters_future_conflicts_and_has_inclusive_boundaries():
    rows = bars([100, 101, 102])
    cutoff = rows[1].available_at
    delayed = replace(rows[1], volume=99, available_at=cutoff + timedelta(seconds=1))
    future = replace(rows[2], currency="USD")
    assert prepare(rows + [delayed, future], as_of=cutoff) == rows[:2]
    assert prepare_history(rows, COMPANY, date(2019, 1, 2), date(2019, 1, 2), cutoff) == rows[1:2]
    # No automatic pre-start warmup leaks into the requested selection.
    selected = prepare_history(wave(), COMPANY, date(2019, 3, 1), date(2019, 3, 10))
    assert len(selected) == 10
    assert all(not series for series in indicator_series(selected).values())
    with pytest.raises(ValueError, match="timezone"):
        prepare(rows, as_of=cutoff.replace(tzinfo=None))


def test_nse_session_dates_handle_utc_midnight_and_end_of_2020():
    timestamp = datetime(2020, 12, 30, 20, tzinfo=timezone.utc)  # Dec 31 in India
    row = replace(bars([100])[0], timestamp=timestamp, available_at=timestamp)
    assert prepare_history([row], COMPANY, date(2020, 12, 31), date(2020, 12, 31)) == [row]
    assert indicator_series([row])["sma20"] == []
    jan1 = replace(
        row, timestamp=timestamp + timedelta(days=1), available_at=timestamp + timedelta(days=1)
    )
    with pytest.raises(ValueError, match="No eligible"):
        prepare_history([jan1], COMPANY, date(2020, 12, 31), date(2020, 12, 31))
    with pytest.raises(ValueError, match="2020-12-31"):
        indicator_series([jan1])
    with pytest.raises(ValueError, match="2020-12-31"):
        run_backtest([row, jan1], "buy_hold")


@pytest.mark.parametrize(
    "change",
    [
        {"volume": 99},
        {"available_at": START + timedelta(hours=1)},
        {"timestamp": START + timedelta(minutes=1)},
    ],
)
def test_conflicting_same_session_is_rejected_in_all_bar_apis(change):
    rows = bars([100, 101])
    conflict = replace(rows[0], **change)
    for call in (prepare, indicator_series, lambda r: run_backtest(r, "buy_hold")):
        with pytest.raises(ValueError, match="same-session"):
            call(rows + [conflict])


@pytest.mark.parametrize("field", ["currency", "unit", "contract_id"])
def test_contract_and_unit_changes_reject_entire_selected_history(field):
    rows = bars([100, 101])
    rows[1] = replace(rows[1], **{field: "changed"})
    for call in (prepare, indicator_series, lambda r: run_backtest(r, "buy_hold")):
        with pytest.raises(ValueError, match="currency/unit/contract"):
            call(rows)


@pytest.mark.parametrize(
    "bounds",
    [
        (date(2020, 1, 1), date(2021, 1, 1)),
        (date(2020, 1, 2), date(2020, 1, 1)),
        ("2019-01-01", date(2020, 1, 1)),
        (START, date(2020, 1, 1)),
    ],
)
def test_history_rejects_invalid_window(bounds):
    with pytest.raises(ValueError):
        prepare_history(bars([100]), COMPANY, *bounds)


def test_empty_and_mixed_series_validation():
    with pytest.raises(ValueError, match="No eligible"):
        prepare([])
    with pytest.raises(ValueError, match="instrument_id"):
        prepare_history([], " ", date(2019, 1, 1), date(2020, 1, 1))
    assert indicator_series([]) == {key: [] for key in MINIMUMS}
    rows = bars([100, 101])
    for changes in ({"instrument_id": "OTHER"}, {"market_family": "benchmark"}):
        with pytest.raises(ValueError, match="one equity"):
            indicator_series([rows[0], replace(rows[1], **changes)])
    # Pydantic's unchecked model_copy must not bypass numerical/bar validation.
    for changes in (
        {"close": float("nan")},
        {"open": -1},
        {"high": 1},
        {"available_at": START - timedelta(days=1)},
    ):
        with pytest.raises(ValueError):
            indicator_series([rows[0].model_copy(update=changes)])


def test_all_indicator_warmups_exactly_and_linear_ramp_known_values():
    rows = bars(list(range(100, 320)))
    result = indicator_series(rows)
    assert set(result) == set(MINIMUMS)
    for key, count in MINIMUMS.items():
        assert len(result[key]) == len(rows) - count + 1
        assert result[key][0]["time"] == rows[count - 1].timestamp.date().isoformat()
        assert indicator_series(rows[: count - 1])[key] == []
        assert len(indicator_series(rows[:count])[key]) == 1
    final = {k: v[-1]["value"] for k, v in result.items()}
    assert final == pytest.approx(
        {
            "sma20": 309.5,
            "sma50": 294.5,
            "sma200": 219.5,
            "ema20": 309.5,
            "ema50": 294.5,
            "rsi14": 100,
            "macd_line": 7,
            "macd_signal": 7,
            "macd_histogram": 0,
            "bollinger20_middle": 309.5,
            "bollinger20_upper": 309.5 + sqrt(133),
            "bollinger20_lower": 309.5 - sqrt(133),
            "atr14": 2,
            "adx14": 100,
        }
    )


def test_every_indicator_prefix_agrees_with_technicals_on_nontrivial_ohlc():
    rows = wave(220)
    result = indicator_series(rows)
    for count in range(1, len(rows) + 1):
        snapshot = compute_technicals(rows[:count], rows[count - 1].available_at, COMPANY)
        prefix = indicator_series(rows[:count])
        for key, value in snapshot.values.items():
            if value is None:
                assert prefix[key] == []
            else:
                assert prefix[key][-1]["value"] == pytest.approx(value, abs=1e-12)
        for key in MINIMUMS:
            assert prefix[key] == [
                p for p in result[key] if p["time"] <= rows[count - 1].timestamp.date().isoformat()
            ]


def test_future_price_volume_and_gap_perturbation_cannot_change_prior_indicators():
    rows = wave()
    cutoff = 85
    changed = rows[:cutoff] + [
        replace(
            row,
            open=1000 + i,
            close=1200 + i,
            high=1500 + i,
            low=900 + i,
            volume=1e12,
        )
        for i, row in enumerate(rows[cutoff:])
    ]
    before, after = indicator_series(rows), indicator_series(changed)
    last = rows[cutoff - 1].timestamp.date().isoformat()
    assert any(before[k] != after[k] for k in MINIMUMS)
    assert {k: [p for p in v if p["time"] <= last] for k, v in after.items()} == indicator_series(
        rows[:cutoff]
    )


def test_flat_declining_shock_rsi_ema_atr_and_directional_seeds():
    flat = indicator_series(bars([100] * 60, spread=0))
    assert flat["rsi14"][-1]["value"] == 50
    assert flat["atr14"][-1]["value"] == flat["adx14"][-1]["value"] == 0
    assert indicator_series(bars(list(range(200, 140, -1))))["rsi14"][-1]["value"] == 0
    shock = indicator_series(bars([100] * 20 + [121]))
    assert shock["ema20"][-1]["value"] == 102
    closes = [100]
    for change in [2, -1] * 7 + [3, -4]:
        closes.append(closes[-1] + change)
    assert indicator_series(bars(closes))["rsi14"][-1]["value"] == pytest.approx(100 * 416 / 697)
    rows = bars([100] * 15 + [110])
    rows[0] = replace(rows[0], high=150, low=50)
    assert indicator_series(rows)["atr14"][-1]["value"] == pytest.approx(37 / 14)
    assert indicator_series(bars(list(range(100, 128)) + [126]))["adx14"][-1][
        "value"
    ] == pytest.approx(4850 / 49)


def test_buy_hold_independent_fee_slippage_benchmark_and_metric_accounting():
    rows = bars([100, 110, 121], opens=[100, 100, 110])
    result = run_backtest(rows, "buy_hold", initial_capital=1000, cost_bps=200, slippage_bps=100)
    # Cash 1000 buys at 101; a 2% notional fee must fit within that cash.
    shares = 1000 / 103.02
    fee = shares * 101 * 0.02
    marked = [1000, shares * 110, shares * 121]
    assert [p["value"] for p in result["equity"]] == pytest.approx(marked)
    assert [p["benchmark"] for p in result["equity"]] == pytest.approx(marked)
    assert len(result["trades"]) == 1  # no synthetic terminal sell
    fill = result["trades"][0]
    assert fill["signal_time"] == "2019-01-01"
    assert fill["time"] == "2019-01-02"
    assert fill["price"] == 101
    assert fill["quantity"] == pytest.approx(shares)
    assert fill["fee"] == pytest.approx(fee)
    assert fill["notional"] + fill["fee"] == pytest.approx(1000)
    assert fill["slippage_cost"] == pytest.approx(shares)
    assert fill["cash_after"] == 0
    assert fill["realized_pnl"] is fill["trade_return"] is None
    returns = [marked[1] / 1000 - 1, 0.1]
    assert result["daily_returns"] == pytest.approx(returns)
    metrics = result["metrics"]
    assert metrics["total_return"] == pytest.approx(marked[-1] / 1000 - 1)
    assert metrics["benchmark_return"] == metrics["total_return"]
    assert metrics["sharpe"] == pytest.approx(sqrt(252) * fmean(returns) / stdev(returns))
    assert metrics["cagr"] == pytest.approx((marked[-1] / 1000) ** (365.25 / 2) - 1)
    assert metrics["max_drawdown"] == 0
    assert metrics["closed_trades"] == 0
    assert metrics["win_rate"] is None
    position = result["open_position"]
    assert position["cost_basis"] == 1000
    assert position["market_value"] == pytest.approx(marked[-1])
    assert position["unrealized_pnl"] == pytest.approx(marked[-1] - 1000)
    json.dumps(result, allow_nan=False)


def test_cross_round_trip_independent_sell_costs_and_reinvestment():
    closes = [100, 90, 80, 100, 110, 70, 60, 120, 130]
    rows = bars(closes, opens=[100, 90, 80, 100, 110, 200, 50, 120, 130])
    result = run_backtest(rows, "sma_cross", 1000, 200, 100, fast_period=2, slow_period=3)
    fills = result["trades"]
    assert [(t["side"], t["time"]) for t in fills] == [
        ("buy", "2019-01-06"),
        ("sell", "2019-01-07"),
        ("buy", "2019-01-09"),
    ]
    shares = 1000 / (202 * 1.02)
    sell_notional = shares * 49.5
    proceeds = sell_notional - sell_notional * 0.02
    second_shares = proceeds / (131.3 * 1.02)
    assert fills[0]["quantity"] == pytest.approx(shares)
    assert fills[1]["price"] == 49.5
    assert fills[1]["fee"] == pytest.approx(sell_notional * 0.02)
    assert fills[1]["realized_pnl"] == pytest.approx(proceeds - 1000)
    assert fills[1]["trade_return"] == pytest.approx(proceeds / 1000 - 1)
    assert fills[2]["quantity"] == pytest.approx(second_shares)
    assert result["metrics"]["final_equity"] == pytest.approx(second_shares * 130)
    assert result["metrics"]["closed_trades"] == 1
    assert result["metrics"]["win_rate"] == 0
    assert result["metrics"]["total_fees"] == pytest.approx(
        shares * 202 * 0.02 + sell_notional * 0.02 + second_shares * 131.3 * 0.02
    )
    assert result["metrics"]["total_slippage"] == pytest.approx(
        shares * 2 + shares * 0.5 + second_shares * 1.3
    )
    # Benchmark independently buys on Jan 2, ignoring the strategy's warmup/exits.
    benchmark_shares = 1000 / (90 * 1.01 * 1.02)
    assert result["equity"][-1]["benchmark"] == pytest.approx(benchmark_shares * 130)
    marks = [1000] * 5 + [shares * 70, proceeds, proceeds, second_shares * 130]
    assert [p["value"] for p in result["equity"]] == pytest.approx(marks)
    peak = 1000
    drawdowns = []
    for value in marks:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1)
    assert result["metrics"]["max_drawdown"] == pytest.approx(min(drawdowns))


def test_win_rate_closed_trade_and_flat_terminal_position():
    # Initial seeded uptrend enters; a close collapse exits on a higher next open.
    rows = bars([100, 101, 102, 80, 120], opens=[100, 101, 102, 100, 130])
    result = run_backtest(rows, "sma_cross", 1000, 0, 0, fast_period=1, slow_period=2)
    assert [(t["side"], t["price"]) for t in result["trades"]] == [("buy", 102), ("sell", 130)]
    assert result["metrics"]["win_rate"] == 1
    assert result["open_position"] is None
    assert result["equity"][-1]["value"] == pytest.approx(1000 * 130 / 102)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_all_strategy_prefixes_are_identical_and_future_perturbations_do_not_leak(strategy):
    rows = wave(190)
    original = [r.model_dump_json() for r in rows]
    full = run_backtest(rows, strategy)
    for count in (51, 63, 87, 120, 151):
        prefix = run_backtest(rows[:count], strategy)
        assert prefix["equity"] == full["equity"][:count]
        assert prefix["daily_returns"] == full["daily_returns"][: count - 1]
        assert prefix["trades"] == [
            t for t in full["trades"] if t["time"] <= prefix["equity"][-1]["time"]
        ]
        changed = rows[:count] + [
            replace(r, open=200, close=170, high=210, low=160, volume=1e9) for r in rows[count:]
        ]
        perturbed = run_backtest(changed, strategy)
        assert perturbed["equity"][:count] == prefix["equity"]
        assert [
            t for t in perturbed["trades"] if t["time"] <= prefix["equity"][-1]["time"]
        ] == prefix["trades"]
    assert [r.model_dump_json() for r in rows] == original
    assert run_backtest(list(reversed(rows)) + [rows[0]], strategy) == full
    json.dumps(full, allow_nan=False)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_fill_quantity_price_side_do_not_use_execution_session_close_or_high_low(strategy):
    rows = wave(200)
    baseline = run_backtest(rows, strategy)
    assert baseline["trades"], f"fixture must exercise {strategy} fills"
    for fill in baseline["trades"][:4]:
        i = next(i for i, r in enumerate(rows) if r.timestamp.date().isoformat() == fill["time"])
        altered = list(rows)
        altered[i] = replace(
            rows[i],
            close=rows[i].close * 4,
            high=max(rows[i].open, rows[i].close * 4) + 100,
            low=rows[i].low / 2,
            volume=1e8,
        )
        result = run_backtest(altered, strategy)
        assert [t for t in result["trades"] if t["time"] <= fill["time"]] == [
            t for t in baseline["trades"] if t["time"] <= fill["time"]
        ]


@pytest.mark.parametrize("strategy", ["sma_cross", "ema_cross"])
def test_first_seed_bullish_entry_and_last_close_signal_unfilled(strategy):
    rows = bars([100, 101, 102, 103, 104])
    result = run_backtest(rows, strategy, cost_bps=0, slippage_bps=0, fast_period=2, slow_period=3)
    assert result["trades"][0]["signal_time"] == "2019-01-03"
    assert result["trades"][0]["time"] == "2019-01-04"
    # A flat warmup and last-close jump generate no executable entry.
    last = run_backtest(bars([100] * 10 + [200]), strategy, fast_period=2, slow_period=3)
    assert last["trades"] == []
    assert all(p["value"] == 100000 for p in last["equity"])
    assert last["metrics"]["sharpe"] is None


def test_reversion_thresholds_and_next_open_known_examples():
    rows = bars(list(range(120, 104, -1)))
    rsi = run_backtest(rows, "rsi_reversion", cost_bps=0, slippage_bps=0)
    assert rsi["trades"][0]["signal_time"] == "2019-01-15"
    assert rsi["trades"][0]["time"] == "2019-01-16"
    bb_rows = bars([100] * 19 + [80, 70, 110, 120])
    bb = run_backtest(bb_rows, "bollinger_reversion", cost_bps=0, slippage_bps=0)
    assert [(t["side"], t["price"]) for t in bb["trades"]] == [("buy", 70), ("sell", 120)]
    assert bb["trades"][1]["signal_time"] == "2019-01-22"


@pytest.mark.parametrize(
    "strategy,count",
    [
        ("buy_hold", 1),
        ("sma_cross", 50),
        ("ema_cross", 50),
        ("rsi_reversion", 15),
        ("macd_cross", 34),
        ("bollinger_reversion", 20),
    ],
)
def test_backtest_requires_warmup_plus_execution_bar(strategy, count):
    with pytest.raises(ValueError, match="requires at least"):
        run_backtest(bars([100] * count), strategy)
    run_backtest(bars([100] * (count + 1)), strategy)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strategy": "unknown"},
        {"initial_capital": 0},
        {"initial_capital": float("inf")},
        {"cost_bps": -1},
        {"cost_bps": 10000},
        {"cost_bps": float("nan")},
        {"slippage_bps": -1},
        {"slippage_bps": 10000},
        {"slippage_bps": float("inf")},
        {"fast_period": 0},
        {"slow_period": 2.5},
        {"fast_period": 50},
        {"fast_period": True},
        {"slow_period": 10001},
        {"rsi_buy": -1},
        {"rsi_sell": 101},
        {"rsi_buy": 70},
        {"rsi_sell": float("nan")},
        {"initial_capital": True},
        {"cost_bps": True},
    ],
)
def test_backtest_rejects_invalid_finite_parameters(kwargs):
    with pytest.raises(ValueError):
        run_backtest(wave(60), **kwargs)


def test_monte_carlo_constant_returns_exact_paths_and_bands():
    result = monte_carlo([0.01] * 10, 1000, simulations=4, horizon=7, block_size=3)
    expected = [1000 * 1.01**i for i in range(8)]
    for path in result["paths"]:
        assert path == pytest.approx(expected)
    for i, band in enumerate(result["bands"]):
        assert band == pytest.approx(
            {"step": i, "p05": expected[i], "p50": expected[i], "p95": expected[i]}
        )
    assert result["metrics"]["probability_loss"] == 0
    assert result["metrics"]["median_terminal"] == pytest.approx(expected[-1])
    zero = monte_carlo([0, 0], 100, 2, 3, block_size=1)
    assert zero["paths"] == [[100] * 4] * 2
    assert zero["metrics"]["probability_loss"] == 0  # equality is not a loss
    loss = monte_carlo([-0.1, -0.1], 100, 2, 3, block_size=1)
    assert loss["metrics"]["probability_loss"] == 1
    json.dumps(result, allow_nan=False)


def test_full_length_blocks_repeat_without_wrap_and_truncate():
    result = monte_carlo([0.1, -0.2, 0.3], 100, 2, 8, seed=999, block_size=3)
    # A full-history block has exactly one valid start, so no randomness remains.
    expected = [100]
    for change in [0.1, -0.2, 0.3, 0.1, -0.2, 0.3, 0.1, -0.2]:
        expected.append(expected[-1] * (1 + change))
    assert result["paths"][0] == pytest.approx(expected)
    assert result["paths"][1] == pytest.approx(expected)
    shorter = monte_carlo([0.1, -0.2, 0.3], 100, 2, 2, block_size=3)
    assert shorter["paths"][0] == pytest.approx([100, 110, 88])


def test_moving_blocks_preserve_order_and_can_sample_last_overlapping_start():
    history = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    result = monte_carlo(history, 100, 100, 8, seed=17, block_size=3)
    starts = set()
    for path in result["paths"]:
        sampled = [b / a - 1 for a, b in zip(path, path[1:])]
        for offset in range(0, 8, 3):
            block = sampled[offset : offset + 3]
            start = min(range(4), key=lambda i: abs(history[i] - block[0]))
            starts.add(start)
            assert block == pytest.approx(history[start : start + len(block)])
    assert starts == {0, 1, 2, 3}


def test_bootstrap_seed_reproducibility_input_immutability_and_global_rng_isolation():
    history = [-0.03, 0.02, 0.01, -0.01, 0.04, -0.02, 0.07]
    original = list(history)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    a = monte_carlo(history, simulations=8, horizon=13, seed=7, block_size=2)
    b = monte_carlo(history, simulations=8, horizon=13, seed=7, block_size=2)
    c = monte_carlo(history, simulations=8, horizon=13, seed=8, block_size=2)
    assert a == b
    assert a["paths"] != c["paths"]
    assert history == original
    assert random.getstate() == python_state
    after = np.random.get_state()
    assert after[0] == numpy_state[0]
    np.testing.assert_array_equal(after[1], numpy_state[1])
    assert after[2:] == numpy_state[2:]


def test_quantiles_loss_and_terminal_metrics_from_independently_sorted_paths():
    result = monte_carlo([-0.5, 0, 0.5], 100, simulations=20, horizon=1, seed=24, block_size=1)
    values = sorted(path[-1] for path in result["paths"])

    def quantile(p):
        index = 19 * p
        lower = int(index)
        upper = min(lower + 1, 19)
        return values[lower] + (values[upper] - values[lower]) * (index - lower)

    assert result["bands"][0] == {"step": 0, "p05": 100, "p50": 100, "p95": 100}
    assert result["bands"][-1] == pytest.approx(
        {"step": 1, "p05": quantile(0.05), "p50": quantile(0.5), "p95": quantile(0.95)}
    )
    assert result["metrics"] == pytest.approx(
        {
            "probability_loss": sum(v < 100 for v in values) / 20,
            "p05_terminal": quantile(0.05),
            "median_terminal": quantile(0.5),
            "p95_terminal": quantile(0.95),
        }
    )
    assert all(b["p05"] <= b["p50"] <= b["p95"] for b in result["bands"])


@pytest.mark.parametrize(
    "returns",
    [
        [],
        [0.1],
        [-1, 0.1],
        [-2, 0.1],
        [float("nan"), 0],
        [float("inf"), 0],
        [True, 0.1],
        [".1", 0.2],
    ],
)
def test_bootstrap_rejects_invalid_history(returns):
    with pytest.raises(ValueError):
        monte_carlo(returns)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"simulations": 0},
        {"simulations": 2001},
        {"simulations": 1.5},
        {"horizon": 0},
        {"horizon": 2521},
        {"horizon": True},
        {"simulations": 2000, "horizon": 2520},
        {"block_size": 0},
        {"block_size": 11},
        {"block_size": 1.2},
        {"seed": -1},
        {"seed": 2**64},
        {"seed": 1.5},
        {"seed": True},
        {"initial_capital": 0},
        {"initial_capital": float("inf")},
    ],
)
def test_bootstrap_bounds_and_numeric_validation(kwargs):
    with pytest.raises(ValueError):
        monte_carlo([0.01] * 10, **kwargs)


def test_extreme_arithmetic_fails_explicitly_instead_of_non_json_numbers():
    with pytest.raises(ValueError):
        monte_carlo([1e300, 1e300], simulations=1, horizon=10, block_size=1)
    with pytest.raises(ValueError):
        monte_carlo([-0.999, -0.999], simulations=1, horizon=2520, block_size=1)
    rows = bars([1, 1e100], opens=[1, 1], spread=0.1)
    with pytest.raises(ValueError, match="finite range"):
        run_backtest(rows, "buy_hold", cost_bps=0, slippage_bps=0)


def test_unrepresentable_integer_capital_is_a_validation_error():
    enormous = 10**1000
    with pytest.raises(ValueError, match="finite number"):
        run_backtest(bars([100, 101]), "buy_hold", initial_capital=enormous)
    with pytest.raises(ValueError, match="finite number"):
        monte_carlo([0.01] * 5, initial_capital=enormous)


def test_buy_hold_matches_benchmark_exactly_for_irregular_prices_and_costs():
    result = run_backtest(wave(60), "buy_hold", cost_bps=13.7, slippage_bps=8.9)
    assert all(p["value"] == p["benchmark"] for p in result["equity"])
    assert result["metrics"]["total_return"] == result["metrics"]["benchmark_return"]


def test_research_functions_work_with_network_model_and_storage_disabled(monkeypatch):
    # Importing/using any provider or persistence dependency would violate this boundary.
    import builtins
    import socket

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"requests", "model_client", "storage", "live_data"} or name.startswith(
            ("market_events.storage", "market_events.model_client", "market_events.live_data")
        ):
            pytest.fail(f"unexpected research dependency: {name}")
        return real_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected network or file call")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    rows = prepare(wave(60))
    indicator_series(rows)
    result = run_backtest(rows)
    monte_carlo(result["daily_returns"], simulations=2, horizon=5)


def _independent_psr(returns):
    """Bailey & Lopez de Prado PSR(0), computed separately with NumPy moments."""
    from statistics import NormalDist

    values = np.asarray(returns, dtype=float)
    centred = values - values.mean()
    m2 = np.mean(centred**2)
    skew = np.mean(centred**3) / m2**1.5
    kurt = np.mean(centred**4) / m2**2
    sr = values.mean() / values.std(ddof=1)
    z = sr * sqrt(len(values) - 1) / sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return NormalDist().cdf(z)


def test_probabilistic_sharpe_matches_formula_and_respects_sample_size():
    returns = [0.012, -0.004, 0.007, 0.001, -0.009, 0.015, 0.003, -0.002, 0.006, 0.011]
    assert probabilistic_sharpe(returns) == pytest.approx(_independent_psr(returns))
    # Same per-session Sharpe with more observations gives more confidence.
    assert probabilistic_sharpe(returns * 4) > probabilistic_sharpe(returns) > 0.5
    # Zero-mean symmetric returns: no evidence either way.
    assert probabilistic_sharpe([0.01, -0.01] * 10) == pytest.approx(0.5)
    assert probabilistic_sharpe([-r for r in returns]) < 0.5
    # Undefined cases are None, never a fabricated number.
    assert probabilistic_sharpe([0.01, 0.02]) is None
    assert probabilistic_sharpe([0.01] * 10) is None


def test_backtest_reports_psr_with_not_deflated_disclosure():
    closes = [100 + 3 * sin(i / 3) + i * 0.1 for i in range(80)]
    result = run_backtest(bars(closes), "buy_hold", initial_capital=1000)
    assert result["metrics"]["probabilistic_sharpe"] == pytest.approx(
        probabilistic_sharpe(result["daily_returns"])
    )
    assert 0 <= result["metrics"]["probabilistic_sharpe"] <= 1
    note = next(a for a in result["assumptions"] if "Probabilistic Sharpe" in a)
    assert "not deflated for the number of configurations tried" in note


def test_walk_forward_runs_the_same_fixed_rule_independently_on_each_segment():
    closes = [100 + 4 * sin(i / 5) + i * 0.05 for i in range(160)]
    rows = bars(closes)
    split = (rows[100].timestamp.date()).isoformat()
    params = {"strategy": "sma_cross", "fast_period": 5, "slow_period": 20, "cost_bps": 10}
    result = walk_forward(rows, date.fromisoformat(split), **params)
    inside = [r for r in rows if r.timestamp.date() < date.fromisoformat(split)]
    outside = [r for r in rows if r.timestamp.date() >= date.fromisoformat(split)]
    assert result["split_date"] == split
    assert result["in_sample"]["bars"] == len(inside) == 100
    assert result["out_of_sample"]["bars"] == len(outside) == 60
    assert result["in_sample"]["actual_end"] < result["out_of_sample"]["actual_start"] == split
    # Each side equals an independent backtest of that segment alone: no leakage.
    assert result["in_sample"]["metrics"] == run_backtest(inside, **params)["metrics"]
    assert result["out_of_sample"]["metrics"] == run_backtest(outside, **params)["metrics"]
    assert any("no parameter was tuned" in note for note in result["assumptions"])


def test_walk_forward_rejects_empty_or_too_short_segments():
    rows = bars([100 + i for i in range(60)])
    first, last = rows[0].timestamp.date(), rows[-1].timestamp.date()
    with pytest.raises(ValueError, match="in-sample segment has no bars"):
        walk_forward(rows, first, strategy="buy_hold")
    with pytest.raises(ValueError, match="out-of-sample segment: sma_cross requires"):
        walk_forward(rows, last, strategy="sma_cross", fast_period=2, slow_period=5)
    with pytest.raises(ValueError, match="split_date must be a date"):
        walk_forward(rows, datetime(2019, 1, 10, tzinfo=timezone.utc), strategy="buy_hold")
