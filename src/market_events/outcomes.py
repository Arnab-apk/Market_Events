"""Separate next-open to fifth-session-close hypothetical long outcomes."""

import math
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from .schemas import AnalysisRun, EventOutcome, MarketObservation, utc


def evaluate_outcome(
    run: AnalysisRun,
    later_observations: list[MarketObservation],
    benchmark_id: str | None = None,
    cost_bps: float = 10.0,
    evaluation_time: datetime | None = None,
) -> EventOutcome:
    """Use finished available bars, five observed sessions including entry.

    Entry is 09:15 Asia/Kolkata on the observed NSE session date, normalized UTC.
    Exit uses the fifth observed session's close timestamp. Observed sessions do
    not establish exchange-calendar completeness; missing sessions cannot be inferred.
    Costs are total round-trip basis points, not per-side. No short inversion.
    """
    now = utc(evaluation_time or datetime.now(timezone.utc))
    exchange_zone = ZoneInfo("Asia/Kolkata")

    def session_open(observation: MarketObservation) -> datetime:
        session_date = observation.timestamp.astimezone(exchange_zone).date()
        return datetime.combine(session_date, time(9, 15), tzinfo=exchange_zone).astimezone(
            timezone.utc
        )

    if not math.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps must be finite and nonnegative")
    company = run.extraction.company_id if run.extraction else None
    if not company or not run.assessment or run.assessment.direction == "abstain":
        return EventOutcome(
            run_id=run.run_id, status="invalid", reason="No eligible assessed company decision"
        )
    if run.config_snapshot.get("corporate_action") or run.config_snapshot.get("corporate_actions"):
        return EventOutcome(
            run_id=run.run_id,
            status="invalid",
            reason="Corporate action requires consistent adjustment support",
        )
    rows = [
        o
        for o in later_observations
        if o.instrument_id == company
        and o.market_family == "equity"
        and run.decision_time < o.timestamp <= now
        and session_open(o) > run.decision_time
    ]
    unique = {o.model_dump_json(): o for o in rows}
    rows = sorted(unique.values(), key=lambda o: o.timestamp)
    sessions = {}
    for row in rows:
        sessions.setdefault(row.timestamp.astimezone(exchange_zone).date(), []).append(row)
    horizon_sessions = list(sessions.values())[:5]
    # Preserve delayed session dates, while ignoring revisions not yet available.
    available_sessions = [
        [o for o in session if o.available_at <= now] for session in horizon_sessions
    ]
    if len(available_sessions) < 5 or any(not session for session in available_sessions):
        return EventOutcome(
            run_id=run.run_id,
            status="pending",
            reason="Five finished, available equity sessions required",
        )
    if any(len(session) != 1 for session in available_sessions):
        return EventOutcome(
            run_id=run.run_id, status="invalid", reason="Conflicting equity sessions"
        )
    horizon = [session[0] for session in available_sessions]
    entry, exit_ = horizon[0], horizon[-1]
    if len({(o.currency, o.unit, o.contract_id) for o in horizon}) != 1:
        return EventOutcome(run_id=run.run_id, status="invalid", reason="Inconsistent price units")
    gross = exit_.close / entry.open - 1
    net = gross - cost_bps / 10000
    bench_return = None
    reason = (
        "Completed five observed sessions; exchange-calendar completeness not verified; "
        "costs are round-trip basis points"
    )
    benchmark = [
        o
        for o in later_observations
        if o.instrument_id == benchmark_id
        and o.market_family == "benchmark"
        and o.timestamp <= now
        and o.available_at <= now
    ]
    starts = {
        o.model_dump_json(): o for o in benchmark if o.timestamp.date() == entry.timestamp.date()
    }
    ends = {
        o.model_dump_json(): o for o in benchmark if o.timestamp.date() == exit_.timestamp.date()
    }
    if len(starts) == len(ends) == 1:
        first, last = next(iter(starts.values())), next(iter(ends.values()))
        if (first.currency, first.unit) == (last.currency, last.unit):
            bench_return = last.close / first.open - 1
    if bench_return is None:
        reason += "; exact-date benchmark unavailable"
    return EventOutcome(
        run_id=run.run_id,
        status="completed",
        entry_time=session_open(entry),
        exit_time=exit_.timestamp,
        entry_price=entry.open,
        exit_price=exit_.close,
        gross_return=gross,
        net_return=net,
        benchmark_return=bench_return,
        excess_return=gross - bench_return if bench_return is not None else None,
        label="positive" if net > 0 else "negative" if net < 0 else "neutral",
        reason=reason,
    )
