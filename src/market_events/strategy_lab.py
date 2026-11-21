"""Calculations behind the strategy lab: history selection, causal indicators, a long/cash backtest
with next-open fills and costs, a probabilistic Sharpe ratio and a block-bootstrap Monte Carlo.
Everything is pure local computation on history ending by 2020-12-31; nothing is persisted or
downloaded here.

Historical availability is preserved, not simulated: these are retrospective OHLC
experiments, not assertions that today's downloaded bars were known in 2020.
Session dates follow Asia/Kolkata, consistently with technicals-v1. No calendar
filling, corporate-action inference, model, provider, or persistence operations.
"""

from datetime import date, datetime, timezone
from math import erf, exp, isfinite, log, sqrt
from numbers import Integral, Real
from statistics import fmean, pstdev, stdev
from zoneinfo import ZoneInfo

import numpy as np

from .schemas import MarketObservation, utc
from .technicals import _directional, _smooth

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HISTORY_END = date(2020, 12, 31)
_EXCHANGE = ZoneInfo("Asia/Kolkata")
_STRATEGIES = {
    "buy_hold",
    "sma_cross",
    "ema_cross",
    "rsi_reversion",
    "macd_cross",
    "bollinger_reversion",
}
_INDICATORS = (
    "sma20",
    "sma50",
    "sma200",
    "ema20",
    "ema50",
    "rsi14",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "bollinger20_middle",
    "bollinger20_upper",
    "bollinger20_lower",
    "atr14",
    "adx14",
)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _session(row: MarketObservation) -> date:
    return row.timestamp.astimezone(_EXCHANGE).date()


def _number(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _integer(value: int, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer in [{lower}, {upper}]")
    return int(value)


def _date(value: date, name: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise ValueError(f"{name} must be a date")
    return value


def _validated_bars(bars: list[MarketObservation]) -> list[MarketObservation]:
    """Validate even model_copy/model_construct inputs; sort without mutating."""
    rows = []
    unique = set()
    sessions = set()
    for row in bars:
        if not isinstance(row, MarketObservation):
            raise ValueError("bars must contain MarketObservation records")
        checked = MarketObservation.model_validate(row.model_dump())
        fingerprint = checked.model_dump_json()
        if fingerprint in unique:
            continue
        unique.add(fingerprint)
        session = _session(checked)
        if session > HISTORY_END:
            raise ValueError("Historical research must end on or before 2020-12-31")
        if session in sessions:
            raise ValueError("Conflicting same-session records")
        sessions.add(session)
        rows.append(checked)
    if len({(r.instrument_id, r.market_family) for r in rows}) > 1:
        raise ValueError("bars must describe one equity instrument")
    if any(r.market_family != "equity" for r in rows):
        raise ValueError("bars must describe one equity instrument")
    if len({(r.currency, r.unit, r.contract_id) for r in rows}) > 1:
        raise ValueError("Inconsistent currency/unit/contract in history")
    return sorted(rows, key=lambda row: row.timestamp)


# ---------------------------------------------------------------------------
# History selection
# ---------------------------------------------------------------------------


def prepare_history(
    observations: list[MarketObservation],
    instrument_id: str,
    start_date: date,
    end_date: date,
    as_of: datetime | None = None,
) -> list[MarketObservation]:
    """Select inclusive session dates and records known by the aware cutoff.

    Only the selected equity and window are checked for conflicts. Exact record
    duplicates collapse; differences including available_at remain conflicts.
    Pass earlier start_date explicitly for warmup; no hidden pre-window bars.
    """
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        raise ValueError("instrument_id must be a nonempty canonical identifier")
    start = _date(start_date, "start_date")
    end = _date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if end > HISTORY_END:
        raise ValueError("Historical research must end on or before 2020-12-31")
    cutoff = utc(as_of if as_of is not None else datetime.now(timezone.utc))
    eligible = []
    for row in observations:
        if not isinstance(row, MarketObservation):
            raise ValueError("observations must contain MarketObservation records")
        if row.instrument_id != instrument_id or row.market_family != "equity":
            continue
        # Normalize timestamps before comparison so naive constructed records fail.
        if utc(row.timestamp) <= cutoff and utc(row.available_at) <= cutoff:
            if start <= _session(row) <= end:
                eligible.append(row)
    rows = _validated_bars(eligible)
    if not rows:
        raise ValueError("No eligible historical bars in the selected window")
    return rows


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def _ma(closes: list[float], period: int, exponential: bool = False) -> list[float | None]:
    values = (
        _smooth(closes, period, 2 / (period + 1))
        if exponential
        else [fmean(closes[i - period + 1 : i + 1]) for i in range(period - 1, len(closes))]
    )
    return [None] * min(period - 1, len(closes)) + values


def _indicator_values(rows: list[MarketObservation]) -> dict[str, list[float | None]]:
    """Aligned technicals-v1 seeds, retaining unavailable warmups as None."""
    n = len(rows)
    closes = [r.close for r in rows]
    values = {key: [None] * n for key in _INDICATORS}

    def align(key: str, offset: int, series: list[float]) -> None:
        values[key][min(offset, n) :] = series

    for period in (20, 50, 200):
        values[f"sma{period}"] = _ma(closes, period)
    for period in (20, 50):
        values[f"ema{period}"] = _ma(closes, period, True)
    changes = [b - a for a, b in zip(closes, closes[1:])]
    gains = _smooth([max(x, 0) for x in changes], 14, 1 / 14)
    losses = _smooth([max(-x, 0) for x in changes], 14, 1 / 14)
    align(
        "rsi14",
        14,
        [100 * (g / (g + loss)) if g + loss else 50.0 for g, loss in zip(gains, losses)],
    )
    fast = _smooth(closes, 12, 2 / 13)
    slow = _smooth(closes, 26, 2 / 27)
    macd = [a - b for a, b in zip(fast[14:], slow)]
    signal = _smooth(macd, 9, 2 / 10)
    align("macd_line", 25, macd)
    align("macd_signal", 33, signal)
    align("macd_histogram", 33, [a - b for a, b in zip(macd[8:], signal)])
    middles = [fmean(closes[i - 19 : i + 1]) for i in range(19, n)]
    deviations = [pstdev(closes[i - 19 : i + 1]) for i in range(19, n)]
    align("bollinger20_middle", 19, middles)
    align("bollinger20_upper", 19, [m + 2 * d for m, d in zip(middles, deviations)])
    align("bollinger20_lower", 19, [m - 2 * d for m, d in zip(middles, deviations)])
    atr, dx = _directional(rows)
    align("atr14", 14, atr)
    align("adx14", 27, _smooth(dx, 14, 1 / 14))
    if any(not isfinite(v) for series in values.values() for v in series if v is not None):
        raise ValueError("Indicator arithmetic produced a nonfinite value")
    return values


def indicator_series(bars: list[MarketObservation]) -> dict[str, list[dict]]:
    """Chart-ready causal series; missing warmups produce no chart point."""
    rows = _validated_bars(bars)
    values = _indicator_values(rows)
    return {
        key: [
            {"time": _session(row).isoformat(), "value": float(value)}
            for row, value in zip(rows, series)
            if value is not None
        ]
        for key, series in values.items()
    }


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


def _signals(rows, strategy, fast_period, slow_period, rsi_buy, rsi_sell):
    """Desired holdings after each close: None means retain current holding."""
    closes = [r.close for r in rows]
    if strategy == "buy_hold":
        return [1] * len(rows)
    if strategy in {"sma_cross", "ema_cross"}:
        fast = _ma(closes, fast_period, strategy == "ema_cross")
        slow = _ma(closes, slow_period, strategy == "ema_cross")
        return [
            None if a is None or b is None or a == b else int(a > b) for a, b in zip(fast, slow)
        ]
    values = _indicator_values(rows)
    signals = []
    for i, close in enumerate(closes):
        desired = None
        if strategy == "rsi_reversion":
            rsi = values["rsi14"][i]
            if rsi is not None:
                desired = 1 if rsi <= rsi_buy else 0 if rsi >= rsi_sell else None
        elif strategy == "macd_cross":
            line, signal = values["macd_line"][i], values["macd_signal"][i]
            if line is not None and signal is not None and line != signal:
                desired = int(line > signal)
        else:
            lower = values["bollinger20_lower"][i]
            middle = values["bollinger20_middle"][i]
            if lower is not None:
                desired = 1 if close < lower else 0 if close >= middle else None
        signals.append(desired)
    return signals


def run_backtest(
    bars: list[MarketObservation],
    strategy: str = "sma_cross",
    initial_capital: float = 100000.0,
    cost_bps: float = 10.0,
    slippage_bps: float = 5.0,
    fast_period: int = 20,
    slow_period: int = 50,
    rsi_buy: float = 30.0,
    rsi_sell: float = 70.0,
) -> dict:
    """All-in fractional-share long/cash strategy, with no forced terminal exit.

    Bullish MA/MACD relationships at their first complete seed enter next open;
    equality retains holdings. RSI enters <= buy, exits >= sell. Bollinger enters
    below lower, exits at/above middle. Last-close signals cannot execute.
    """
    if not isinstance(strategy, str) or strategy not in _STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(_STRATEGIES)}")
    capital = _number(initial_capital, "initial_capital", positive=True)
    fee_rate = _number(cost_bps, "cost_bps") / 10000
    slip = _number(slippage_bps, "slippage_bps") / 10000
    if not 0 <= fee_rate < 1 or not 0 <= slip < 1:
        raise ValueError("cost_bps and slippage_bps must be in [0, 10000)")
    fast_period = _integer(fast_period, "fast_period", 1, 10000)
    slow_period = _integer(slow_period, "slow_period", 2, 10000)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")
    rsi_buy = _number(rsi_buy, "rsi_buy")
    rsi_sell = _number(rsi_sell, "rsi_sell")
    if not 0 <= rsi_buy < rsi_sell <= 100:
        raise ValueError("RSI thresholds must satisfy 0 <= rsi_buy < rsi_sell <= 100")
    rows = _validated_bars(bars)
    minimum = {
        "buy_hold": 2,
        "sma_cross": slow_period + 1,
        "ema_cross": slow_period + 1,
        "rsi_reversion": 16,
        "macd_cross": 35,
        "bollinger_reversion": 21,
    }[strategy]
    if len(rows) < minimum:
        raise ValueError(
            f"{strategy} requires at least {minimum} bars including next-open execution"
        )
    signals = _signals(rows, strategy, fast_period, slow_period, rsi_buy, rsi_sell)
    cash, quantity = capital, 0.0
    benchmark_quantity = 0.0
    entry = None
    trades, equity, closed_pnl = [], [], []
    total_fees = total_slippage = 0.0
    for i, row in enumerate(rows):
        time = _session(row).isoformat()
        desired = signals[i - 1] if i else None
        if i == 1:
            benchmark_quantity = (capital / (row.open * (1 + slip))) / (1 + fee_rate)
        if desired is not None and bool(desired) != bool(quantity):
            side = "buy" if desired else "sell"
            price = row.open * (1 + slip if desired else 1 - slip)
            if desired:
                cost_basis = cash
                quantity = (cash / price) / (1 + fee_rate)
                notional = quantity * price
                fee = notional * fee_rate
                cash = 0.0
                realized_pnl = trade_return = None
                entry = {
                    "entry_time": time,
                    "entry_price": price,
                    "entry_fee": fee,
                    "cost_basis": cost_basis,
                }
                filled_quantity = quantity
            else:
                filled_quantity = quantity
                notional = quantity * price
                fee = notional * fee_rate
                cash = notional - fee
                realized_pnl = cash - entry["cost_basis"]
                trade_return = cash / entry["cost_basis"] - 1
                closed_pnl.append(realized_pnl)
                quantity, entry = 0.0, None
            slippage_cost = filled_quantity * abs(price - row.open)
            total_fees += fee
            total_slippage += slippage_cost
            trades.append(
                {
                    "time": time,
                    "signal_time": _session(rows[i - 1]).isoformat(),
                    "side": side,
                    "quantity": filled_quantity,
                    "price": price,
                    "reference_price": row.open,
                    "notional": notional,
                    "fee": fee,
                    "slippage_cost": slippage_cost,
                    "cash_after": cash,
                    "realized_pnl": realized_pnl,
                    "trade_return": trade_return,
                }
            )
        value = cash + quantity * row.close
        benchmark = capital if i == 0 else benchmark_quantity * row.close
        if not isfinite(value) or value <= 0 or not isfinite(benchmark) or benchmark <= 0:
            raise ValueError("Backtest equity must remain finite and positive")
        equity.append({"time": time, "value": value, "benchmark": benchmark})
    daily_returns = [b["value"] / a["value"] - 1 for a, b in zip(equity, equity[1:])]
    peak, drawdown = capital, 0.0
    for point in equity:
        peak = max(peak, point["value"])
        drawdown = min(drawdown, point["value"] / peak - 1)
    years = (_session(rows[-1]) - _session(rows[0])).days / 365.25
    try:
        cagr = exp(log(equity[-1]["value"] / capital) / years) - 1
        volatility = stdev(daily_returns) if len(daily_returns) > 1 else 0.0
        sharpe = sqrt(252) * fmean(daily_returns) / volatility if volatility else None
        psr = probabilistic_sharpe(daily_returns)
    except (OverflowError, ValueError, ZeroDivisionError):
        raise ValueError("Backtest metric arithmetic exceeds finite range") from None
    metrics = {
        "total_return": equity[-1]["value"] / capital - 1,
        "benchmark_return": equity[-1]["benchmark"] / capital - 1,
        "max_drawdown": drawdown,
        "sharpe": sharpe,
        "probabilistic_sharpe": psr,
        "cagr": cagr,
        "closed_trades": len(closed_pnl),
        "win_rate": sum(p > 0 for p in closed_pnl) / len(closed_pnl) if closed_pnl else None,
        "final_equity": equity[-1]["value"],
        "total_fees": total_fees,
        "total_slippage": total_slippage,
    }
    open_position = (
        {
            **entry,
            "quantity": quantity,
            "mark_price": rows[-1].close,
            "market_value": quantity * rows[-1].close,
            "unrealized_pnl": quantity * rows[-1].close - entry["cost_basis"],
        }
        if entry
        else None
    )
    result = {
        "strategy": strategy,
        "equity": equity,
        "trades": trades,
        "daily_returns": daily_returns,
        "metrics": metrics,
        "open_position": open_position,
        "assumptions": [
            "Retrospective OHLC research only; recorded availability is not historical point-in-time knowledge.",
            "History ends on or before 2020-12-31; NSE session dates; observed sessions only, no calendar filling.",
            "Close signals execute only at the next observed session open; final-close signals are unfilled.",
            "Long/cash with fractional shares, full reinvestment, no leverage, interest, dividends or taxes.",
            "Buy fill=open*(1+slippage_bps/10000); sell fill=open*(1-slippage_bps/10000).",
            "Each fill pays cost_bps/10000 times slipped notional; buy sizing includes that fee.",
            "Final positions are marked at the last close, with no forced exit or hypothetical exit charges.",
            "Benchmark signals at the first close, buys next open with the same costs, and remains marked long.",
            "MA/MACD first seeded bullish relationship enters; equality retains holdings. Warmup stays cash.",
            "RSI enters at/below buy and exits at/above sell; Bollinger enters below lower and exits at/above middle.",
            "Sharpe uses sample deviation of observed close-equity returns, zero risk-free rate and sqrt(252).",
            "Probabilistic Sharpe (Bailey & López de Prado) is P(true per-session Sharpe > 0) given n, skewness and kurtosis; single configuration; not deflated for the number of configurations tried.",
            "CAGR uses elapsed calendar days/365.25; drawdown is a nonpositive fraction from the running equity peak.",
            "Unadjusted OHLC/corporate actions, missing sessions/gaps and survivorship bias can distort results; verify upstream adjustments.",
        ],
    }
    _finite_result(result)
    return result


# ---------------------------------------------------------------------------
# Backtest statistics and finite-result checks
# ---------------------------------------------------------------------------


def probabilistic_sharpe(returns: list[float], benchmark_sharpe: float = 0.0) -> float | None:
    """Probabilistic Sharpe ratio, Bailey & López de Prado (2012/2014).

    PSR(SR*) = Phi((SR - SR*) * sqrt(n - 1) / sqrt(1 - g3*SR + (g4 - 1)/4 * SR^2)),
    where SR is the per-period (non-annualised) Sharpe using the sample standard
    deviation (matching the reported Sharpe), g3 the moment skewness and g4 the
    moment (non-excess) kurtosis of the same returns. SR* is per period. It is a
    single-configuration statistic: it is not deflated for the number of
    configurations tried. Returns None when undefined (n < 3, zero variance or a
    nonpositive variance term).
    """
    n = len(returns)
    if n < 3:
        return None
    average = fmean(returns)
    deviation = stdev(returns)
    if not deviation:
        return None
    centred = [r - average for r in returns]
    m2 = fmean([c * c for c in centred])
    if not m2:
        return None
    skewness = fmean([c**3 for c in centred]) / m2**1.5
    kurtosis = fmean([c**4 for c in centred]) / m2**2
    sharpe = average / deviation
    variance = 1 - skewness * sharpe + (kurtosis - 1) / 4 * sharpe**2
    if not isfinite(variance) or variance <= 0:
        return None
    z = (sharpe - benchmark_sharpe) * sqrt(n - 1) / sqrt(variance)
    return 0.5 * (1 + erf(z / sqrt(2)))


def walk_forward(bars: list[MarketObservation], split_date: date, **parameters) -> dict:
    """Split-sample check of one fixed configuration: in-sample vs out-of-sample.

    Bars before ``split_date`` form the in-sample segment and bars on or after it the
    out-of-sample segment. The same pre-chosen ``parameters`` (run_backtest keyword
    arguments) are run independently on each segment: each starts in cash with its own
    warm-up, so no out-of-sample bar informs the in-sample result or vice versa.
    Nothing is optimised; this only shows whether a fixed rule behaves similarly on
    unseen later data.
    """
    split = _date(split_date, "split_date")
    rows = _validated_bars(bars)
    segments = {
        "in_sample": [row for row in rows if _session(row) < split],
        "out_of_sample": [row for row in rows if _session(row) >= split],
    }
    result = {"split_date": split.isoformat()}
    for name, segment in segments.items():
        if not segment:
            raise ValueError(f"The {name.replace('_', '-')} segment has no bars; move the split")
        try:
            backtest = run_backtest(segment, **parameters)
        except ValueError as error:
            raise ValueError(f"{name.replace('_', '-')} segment: {error}") from None
        result[name] = {
            "actual_start": _session(segment[0]).isoformat(),
            "actual_end": _session(segment[-1]).isoformat(),
            "bars": len(segment),
            "metrics": backtest["metrics"],
            "open_position": backtest["open_position"] is not None,
        }
    result["assumptions"] = [
        "One fixed configuration chosen in advance; no parameter was tuned on either segment.",
        "Each segment is an independent backtest that starts in cash with its own warm-up.",
        "The out-of-sample segment begins on split_date; the in-sample segment ends before it.",
        "A single split is a robustness check, not proof of a persistent edge.",
    ]
    return result


def _finite_result(value) -> None:
    """Do not emit NaN/Infinity through the JSON interface, including on overflow."""
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Result arithmetic exceeds finite range")
    if isinstance(value, dict):
        for item in value.values():
            _finite_result(item)
    elif isinstance(value, list):
        for item in value:
            _finite_result(item)


# ---------------------------------------------------------------------------
# Monte Carlo bootstrap
# ---------------------------------------------------------------------------


def monte_carlo(
    daily_returns: list[float],
    initial_capital: float = 100000.0,
    simulations: int = 300,
    horizon: int = 252,
    seed: int = 42,
    block_size: int = 5,
) -> dict:
    """Local PCG64 RNG, overlapping non-circular moving-block bootstrap.

    Each path samples uniform block starts from 0..n-block_size, concatenates
    blocks and truncates at horizon. No wrap-around, recentering or normal fit.
    """
    capital = _number(initial_capital, "initial_capital", positive=True)
    simulations = _integer(simulations, "simulations", 1, 2000)
    horizon = _integer(horizon, "horizon", 1, 2520)
    seed = _integer(seed, "seed", 0, 2**64 - 1)
    if simulations * (horizon + 1) > 2_000_000:
        raise ValueError("simulations * (horizon + 1) must not exceed 2000000")
    returns = [_number(r, "daily_returns") for r in daily_returns]
    if len(returns) < 2 or any(r <= -1 for r in returns):
        raise ValueError("Require at least two returns, each strictly greater than -1")
    block_size = _integer(block_size, "block_size", 1, len(returns))
    rng = np.random.Generator(np.random.PCG64(seed))
    blocks = (horizon + block_size - 1) // block_size
    starts = rng.integers(0, len(returns) - block_size + 1, size=(simulations, blocks))
    # Construct one path at a time to bound temporary memory even for large blocks.
    paths = np.empty((simulations, horizon + 1), dtype=float)
    paths[:, 0] = capital
    history = np.asarray(returns, dtype=float)
    offsets = np.arange(min(block_size, horizon))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            for i, path_starts in enumerate(starts):
                sampled = history[(path_starts[:, None] + offsets).ravel()[:horizon]]
                paths[i, 1:] = capital * np.cumprod(1 + sampled)
    except FloatingPointError:
        raise ValueError("Monte Carlo path arithmetic exceeds finite range") from None
    if not np.isfinite(paths).all() or (paths <= 0).any():
        raise ValueError("Monte Carlo paths must remain finite and positive")
    quantiles = np.quantile(paths, [0.05, 0.5, 0.95], axis=0, method="linear")
    result = {
        "paths": paths.tolist(),
        "bands": [
            {"step": i, "p05": float(q[0]), "p50": float(q[1]), "p95": float(q[2])}
            for i, q in enumerate(quantiles.T)
        ],
        "metrics": {
            "probability_loss": float(np.mean(paths[:, -1] < capital)),
            "p05_terminal": float(quantiles[0, -1]),
            "median_terminal": float(quantiles[1, -1]),
            "p95_terminal": float(quantiles[2, -1]),
        },
        "assumptions": [
            "Seeded local PCG64 generator; uniform overlapping moving blocks sampled with replacement, without wrap-around.",
            "Blocks are concatenated and truncated to horizon; each path includes initial capital at step zero.",
            "Linear empirical p05/p50/p95 quantiles across paths at each step; losses mean terminal wealth below initial capital.",
            "Resamples historical arithmetic portfolio returns without recentering; input costs are already reflected, no extra fees.",
            "Only within-block serial dependence is preserved; regime changes, gaps and survivorship can invalidate extrapolation.",
            "Empirical scenario frequencies are not probabilities of future market outcomes or financial advice.",
        ],
    }
    _finite_result(result)
    return result
