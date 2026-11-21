"""Market evidence at a decision cutoff. From observations that existed and were available by the
cutoff, it computes the latest equity, benchmark, excess and commodity daily returns plus
relative volume. Missing or stale inputs stay explicit so fusion can abstain instead of guessing.
"""

from datetime import datetime, timedelta

from .schemas import MarketFeatures, MarketObservation, utc


def compute_market_features(
    observations: list[MarketObservation],
    decision_time: datetime,
    company_id: str | None = None,
    commodity_id: str | None = None,
    benchmark_id: str | None = None,
) -> MarketFeatures:
    """Both observation and availability must precede cutoff. No contract rolling.

    A series with conflicting duplicate sessions or multiple commodity contracts is
    unavailable. Stale values remain auditable but fusion must gate them out.
    """
    cutoff = utc(decision_time)
    values = dict.fromkeys(
        [
            "equity_return",
            "benchmark_return",
            "excess_return",
            "relative_volume",
            "commodity_return",
        ]
    )
    used: set[str] = set()
    stale: set[str] = set()

    def series(identifier, family):
        rows = [
            o
            for o in observations
            if identifier
            and o.instrument_id == identifier
            and o.market_family == family
            and o.timestamp <= cutoff
            and o.available_at <= cutoff
        ]
        unique = {o.model_dump_json(): o for o in rows}
        rows = sorted(unique.values(), key=lambda o: o.timestamp)
        if family == "commodity" and len({o.contract_id for o in rows}) > 1:
            return []
        if len({o.timestamp.date() for o in rows}) != len(rows):
            return []
        return rows

    def returns(rows, key):
        if len(rows) < 2:
            return
        pair = rows[-2:]
        if any(
            (o.currency, o.unit, o.contract_id)
            != (pair[0].currency, pair[0].unit, pair[0].contract_id)
            for o in pair
        ):
            return
        values[key] = pair[1].close / pair[0].close - 1
        used.update(o.observation_id for o in pair)
        if cutoff - pair[-1].timestamp > timedelta(days=4):
            stale.add(key)

    equity = series(company_id, "equity")
    benchmark = series(benchmark_id, "benchmark")
    commodity = series(commodity_id, "commodity")
    returns(equity, "equity_return")
    # Benchmark must cover exactly the equity return interval, not its own latest pair.
    if len(equity) >= 2:
        dates = [o.timestamp.date() for o in equity[-2:]]
        aligned = [o for o in benchmark if o.timestamp.date() in dates]
        if [o.timestamp.date() for o in aligned] == dates:
            returns(aligned, "benchmark_return")
    if values["equity_return"] is not None and values["benchmark_return"] is not None:
        values["excess_return"] = values["equity_return"] - values["benchmark_return"]
        if stale & {"equity_return", "benchmark_return"}:
            stale.add("excess_return")
    if len(equity) >= 6:
        baseline = sum(o.volume for o in equity[-6:-1]) / 5
        if baseline > 0:
            values["relative_volume"] = equity[-1].volume / baseline
            used.update(o.observation_id for o in equity[-6:])
            if cutoff - equity[-1].timestamp > timedelta(days=4):
                stale.add("relative_volume")
    # Commodity and equity daily windows must share session dates when both exist.
    if len(commodity) >= 2 and (
        len(equity) < 2
        or [o.timestamp.date() for o in commodity[-2:]] == [o.timestamp.date() for o in equity[-2:]]
    ):
        returns(commodity, "commodity_return")
    return MarketFeatures(
        decision_time=cutoff,
        company_id=company_id,
        values=values,
        observation_ids=sorted(used),
        missing=[k for k, v in values.items() if v is None],
        stale=sorted(stale),
    )
