"""Technical indicator snapshot for one company at a cutoff (SMA, EMA, RSI, MACD, Bollinger, ATR,
ADX). It only uses bars that existed and were available by the cutoff and is saved with each run
as context; it never changes the event score and is not trading advice.

Version technicals-v1 uses closes for SMA/EMA/RSI/MACD/Bollinger, and OHLC
for ATR/ADX. Only the requested equity's timestamp AND available_at <= cutoff
are eligible. Exact duplicate records collapse; conflicting NSE session dates
or any currency/unit/contract change invalidate the entire eligible series.
Observed sessions are counted without forward filling or asserting exchange
calendar completeness. Corporate-action adjustments must be consistent upstream;
they cannot be inferred from OHLC. All recursive indicators use the full eligible
history, so their seeds and supporting observation IDs remain reproducible.

Frozen seeds and minimum bar counts:
* SMA20/50: arithmetic mean of the latest 20/50 closes.
* EMA20: first 20-close SMA, then alpha=2/21 (20 bars minimum).
* RSI14: means of the first 14 close changes (15 bars), then Wilder alpha=1/14.
  Gains/losses are nonnegative; losses-only=0, gains-only=100, both zero=50.
* MACD: independently SMA-seeded EMA12 minus EMA26 (26 bars). Signal9 is
  SMA-seeded from the first nine available MACD values (34 bars); histogram
  is line minus signal. No provisional pre-seed values are exposed.
* Bollinger20: latest 20-close SMA +/- 2 population standard deviations, ddof=0.
* ATR14: mean of 14 true ranges requiring previous closes (15 bars), then
  Wilder alpha=1/14. The initial bar supplies previous close, not an invented TR.
* ADX14: Wilder-smoothed mean TR/+DM/-DM, seeded on the first 14 transitions.
  +DM wins only when high rise is positive and exceeds low fall; -DM is symmetric;
  ties give both zero. DX is 100*abs(+DI--DI)/(+DI+-DI). Zero TR or zero DI sum
  gives DX=0. First ADX is the mean of 14 DX values (bars 15..28), then Wilder
  smoothing. Thus ADX needs 28 bars; flat movement gives a genuine ADX=0.

Example: closes 100..159 have SMA20=149.5, SMA50=134.5, EMA20=149.5,
MACD line/signal=7, histogram=0, RSI14=100. High/low=close+/-1 gives ATR14=2
and ADX14=100. Missing warm-ups are None, never zero. Computed values older
than four calendar days remain auditable but are listed in stale and their
interpretations withheld. Warm-up counts are minimum definitions, not convergence
guarantees; these explicit seeds can differ from chart packages' hidden histories.

Formula references (no runtime network access):
https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/ema
https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd
https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr
https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI
https://www.tradingview.com/support/solutions/43000589099-average-directional-index-adx/
https://www.bollingerbands.com/bollinger-bands
"""

from datetime import datetime, timedelta
from statistics import fmean, pstdev
from zoneinfo import ZoneInfo

from .schemas import MarketObservation, TechnicalSnapshot, utc

REQUIRED_HISTORY = {
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


def _smooth(values: list[float], period: int, alpha: float) -> list[float]:
    """Return only seeded values, starting at input index period-1."""
    if len(values) < period:
        return []
    result = [fmean(values[:period])]
    for value in values[period:]:
        result.append(result[-1] + alpha * (value - result[-1]))
    return result


def _directional(rows: list[MarketObservation]) -> tuple[list[float], list[float]]:
    """Aligned Wilder ATR and DX series, both first defined at equity bar 15."""
    ranges, plus, minus = [], [], []
    for previous, current in zip(rows, rows[1:]):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
        up = current.high - previous.high
        down = previous.low - current.low
        plus.append(up if up > down and up > 0 else 0.0)
        minus.append(down if down > up and down > 0 else 0.0)
    atr = _smooth(ranges, 14, 1 / 14)
    plus = _smooth(plus, 14, 1 / 14)
    minus = _smooth(minus, 14, 1 / 14)
    dx = []
    for true_range, up, down in zip(atr, plus, minus):
        # The common TR denominator cancels in the DX ratio. Compute normalized
        # DI explicitly so the zero-range convention is visible.
        plus_di = 100 * (up / true_range) if true_range else 0.0
        minus_di = 100 * (down / true_range) if true_range else 0.0
        total = plus_di + minus_di
        dx.append(100 * abs(plus_di - minus_di) / total if total else 0.0)
    return atr, dx


def _interpret(key: str, value: float, close: float) -> str:
    """Describe current relationships without claiming a historical crossover."""
    if key == "rsi14":
        level = "elevated" if value >= 70 else "low" if value <= 30 else "mid-range"
        return f"RSI14 is {level}; a 0..100 recent-gain/loss measure, not a reversal forecast."
    if key == "adx14":
        return "Wilder ADX14 measures directional-movement strength, not trend direction."
    if key == "atr14":
        return "Wilder ATR14 measures movement magnitude including gaps, in price units."
    if key == "macd_line":
        position = "above" if value > 0 else "below" if value < 0 else "equal to"
        return f"EMA12 is {position} EMA26; this is context, not a crossover claim."
    if key == "macd_signal":
        return "Nine-period EMA of the available MACD line, seeded by its first nine values."
    if key == "macd_histogram":
        position = "above" if value > 0 else "below" if value < 0 else "equal to"
        return f"MACD line is {position} its signal; a current difference, not a trade instruction."
    position = "above" if close > value else "below" if close < value else "equal to"
    return f"Latest eligible close is {position} {key}; historical price context only."


def compute_technicals(
    observations: list[MarketObservation], decision_time: datetime, company_id: str
) -> TechnicalSnapshot:
    """Calculate the latest seeded indicators from one unambiguous eligible series."""
    cutoff = utc(decision_time)
    if not company_id or not company_id.strip():
        raise ValueError("company_id must be a nonempty canonical identifier")
    eligible = [
        row
        for row in observations
        if row.instrument_id == company_id
        and row.market_family == "equity"
        and row.timestamp <= cutoff
        and row.available_at <= cutoff
    ]
    unique = {row.model_dump_json(): row for row in eligible}
    rows = sorted(unique.values(), key=lambda row: (row.timestamp, row.model_dump_json()))
    values = dict.fromkeys(REQUIRED_HISTORY)
    exchange = ZoneInfo("Asia/Kolkata")
    session_dates = {row.timestamp.astimezone(exchange).date() for row in rows}
    problem = None
    if len(session_dates) != len(rows):
        problem = "Conflicting eligible daily sessions; ambiguous series withheld."
    elif len({(row.currency, row.unit, row.contract_id) for row in rows}) > 1:
        problem = "Inconsistent currency/unit/contract in eligible history; series withheld."
    if rows and problem is None:
        closes = [row.close for row in rows]
        for period in (20, 50):
            if len(closes) >= period:
                values[f"sma{period}"] = fmean(closes[-period:])
        ema20 = _smooth(closes, 20, 2 / 21)
        if ema20:
            values["ema20"] = ema20[-1]
        if len(closes) >= 15:
            changes = [current - previous for previous, current in zip(closes, closes[1:])]
            gain = _smooth([max(change, 0) for change in changes], 14, 1 / 14)[-1]
            loss = _smooth([max(-change, 0) for change in changes], 14, 1 / 14)[-1]
            values["rsi14"] = 100 * (gain / (gain + loss)) if gain + loss else 50.0
        ema12 = _smooth(closes, 12, 2 / 13)
        ema26 = _smooth(closes, 26, 2 / 27)
        macd = [fast - slow for fast, slow in zip(ema12[14:], ema26)]
        if macd:
            values["macd_line"] = macd[-1]
        signal = _smooth(macd, 9, 2 / 10)
        if signal:
            values["macd_signal"] = signal[-1]
            values["macd_histogram"] = macd[-1] - signal[-1]
        if len(closes) >= 20:
            middle = values["sma20"]
            deviation = pstdev(closes[-20:])
            values["bollinger20_middle"] = middle
            values["bollinger20_upper"] = middle + 2 * deviation
            values["bollinger20_lower"] = middle - 2 * deviation
        atr, dx = _directional(rows)
        if atr:
            values["atr14"] = atr[-1]
        adx = _smooth(dx, 14, 1 / 14)
        if adx:
            values["adx14"] = adx[-1]
    stale = (
        sorted(key for key, value in values.items() if value is not None)
        if rows and cutoff - rows[-1].timestamp > timedelta(days=4)
        else []
    )
    interpretation = {
        "context": "Historical technical observations only; not buy/sell advice or probabilities."
    }
    for key, value in values.items():
        if problem:
            interpretation[key] = problem
        elif value is None:
            interpretation[key] = (
                f"Unavailable: requires {REQUIRED_HISTORY[key]} eligible observed bars; "
                f"only {len(rows)} available. No warm-up filling."
            )
        elif key in stale:
            interpretation[key] = (
                "Stale: latest eligible close is older than four calendar days; context withheld."
            )
        else:
            interpretation[key] = _interpret(key, value, rows[-1].close)
    return TechnicalSnapshot(
        decision_time=cutoff,
        company_id=company_id,
        values=values,
        missing=sorted(key for key, value in values.items() if value is None),
        stale=stale,
        observation_ids=sorted({row.observation_id for row in rows}),
        history_bars=len(session_dates),
        required_history=dict(REQUIRED_HISTORY),
        interpretation=interpretation,
        definition_version="technicals-v1",
    )
