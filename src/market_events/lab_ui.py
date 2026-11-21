"""Explicit-action Streamlit research UI over the frozen quant and data APIs."""

import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from .chart_widgets import hosted_chart_html, local_chart_html, monte_carlo_html, ohlc_rows
from .live_data import get_live_universe, sync_historical
from .strategy_lab import HISTORY_END, indicator_series, monte_carlo, prepare_history, run_backtest

PREFIX = "strategy_lab:"
INDICATORS = {
    "SMA 20": "sma20",
    "SMA 50": "sma50",
    "SMA 200": "sma200",
    "EMA 20": "ema20",
    "EMA 50": "ema50",
    "RSI 14": "rsi14",
    "MACD": "MACD",
    "Bollinger bands": "Bollinger",
    "ATR 14": "atr14",
    "ADX 14": "adx14",
    "Volume": "volume",
}
STRATEGIES = {
    "SMA crossover": "sma_cross",
    "EMA crossover": "ema_cross",
    "Buy and hold": "buy_hold",
    "RSI reversion": "rsi_reversion",
    "MACD crossover": "macd_cross",
    "Bollinger reversion": "bollinger_reversion",
}


def _key(name):
    return PREFIX + name


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def workspace_key(dependencies):
    settings = dependencies.settings
    return (
        str(Path(settings.root).resolve()),
        str(Path(settings.database_path).resolve()),
        settings.universe,
    )


def scope_results(state, scope):
    """Invalidate results atomically when the study, history or workspace changes."""
    if state.get(_key("scope")) != scope:
        for name in ("backtest", "simulation", "simulation_scope"):
            state.pop(_key(name), None)
        state[_key("scope")] = scope


def result_manifest(bars, params, start, end, *, kind="backtest", parent=None):
    return dict(
        schema_version="strategy-lab-v1",
        kind=kind,
        created_at=datetime.now(timezone.utc).isoformat(),
        params=params,
        study_dates={
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "actual_start": ohlc_rows(bars)[0]["time"],
            "actual_end": ohlc_rows(bars)[-1]["time"],
        },
        instrument_id=bars[0].instrument_id,
        currency=bars[0].currency,
        unit=bars[0].unit,
        supporting_observation_ids=[r.observation_id for r in bars],
        history_fingerprint=fingerprint([r.model_dump(mode="json") for r in bars]),
        parent_backtest=parent,
        warmup="Selected window only; warmup stays cash.",
        evidence="Retrospective research; availability is never backdated.",
        synthetic=bars[0].instrument_id.startswith("SYNTHETIC:"),
    )


def csv_text(rows):
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _json_download(label, result, filename):
    st.download_button(
        label,
        json.dumps(result, indent=2, allow_nan=False),
        file_name=filename,
        mime="application/json",
        key=_key(filename),
    )


def _percent(value):
    return "Not available" if value is None else f"{value:.2%}"


def _history_form(dependencies, workspace):
    st.subheader("1 · Historical data")
    st.caption(
        "Download daily candles explicitly. Default study: 2015–2020. No news or model calls."
    )
    try:
        equities = [
            x for x in get_live_universe(dependencies.settings) if x["market_family"] == "equity"
        ]
    except (ValueError, OSError):
        equities = []
        st.warning(
            "Historical download configuration is unavailable. Check configs/live_universe.json."
        )
    token_present = bool(dependencies.settings.live_data.access_token.get_secret_value().strip())
    if not token_present:
        st.info(
            "Upstox credentials are missing. Configure UPSTOX_ACCESS_TOKEN or "
            "UPSTOX_ANALYTICS_TOKEN in Connections / the local environment, then reload the workspace. "
            "Existing local history remains usable."
        )
    labels = {x["instrument_id"]: f"{x['name']} · {x['instrument_id']}" for x in equities}
    with st.form(_key("historical_form")):
        selected = st.multiselect(
            "Instruments to download",
            list(labels),
            default=list(labels)[:1],
            format_func=labels.get,
            key=_key("download_ids"),
        )
        left, right = st.columns(2)
        start = left.date_input(
            "Download start",
            date(2015, 1, 1),
            min_value=date(2000, 1, 1),
            max_value=HISTORY_END,
            key=_key("download_start"),
        )
        end = right.date_input(
            "Download end (through 2020)",
            HISTORY_END,
            min_value=date(2000, 1, 1),
            max_value=HISTORY_END,
            key=_key("download_end"),
        )
        submitted = st.form_submit_button("Download historical candles", type="primary")
    if submitted:
        if start > end:
            st.error("Download start must be on or before download end.")
        elif not selected:
            st.error("Select at least one instrument to download.")
        else:
            with st.spinner("Requesting historical candles…"):
                report = sync_historical(dependencies, selected, start, end)
            st.session_state[_key("download_report")] = (workspace, report)
    saved = st.session_state.get(_key("download_report"))
    if saved and saved[0] == workspace:
        report = saved[1]
        for error in report.get("errors", []):
            st.warning(
                f"{error.get('stage', 'download')}: {error.get('message', 'Download failed')}"
            )
        for warning in report.get("warnings", []):
            st.warning(str(warning))
        st.caption(
            f"{report.get('observations_added', 0)} observations added · "
            f"{report.get('network_requests', 0)} provider requests. "
            "Coverage describes this download, not all stored history."
        )
        if report.get("coverage"):
            st.dataframe(
                [dict(instrument_id=k, **v) for k, v in report["coverage"].items()],
                hide_index=True,
                use_container_width=True,
            )
        _json_download("Download history receipt (JSON)", report, "history-receipt.json")


def _hosted_chart():
    with st.expander("Independent TradingView chart · optional"):
        st.caption(
            "External service with independent data and network requests. "
            "Its data may extend beyond 2020 and never enters local backtests."
        )
        enabled = st.checkbox("Load external TradingView hosted widget", key=_key("hosted"))
        if enabled:
            symbol = st.text_input(
                "TradingView exchange:ticker", "NSE:RELIANCE", key=_key("hosted_symbol")
            )
            try:
                components.html(hosted_chart_html(symbol), height=620, scrolling=True)
            except ValueError as error:
                st.warning(str(error))


def render_strategy_lab(dependencies):
    """No provider/model calls except an explicit historical form submission."""
    st.subheader("Strategy lab")
    st.caption("LOCAL RESEARCH · Historical cutoff 2020-12-31 · Retrospective OHLC experiments")
    st.write(
        "Explore price structure, test a rule, then inspect how resampled returns vary. "
        "Results describe the selected observations; they are not investment forecasts."
    )
    workspace = workspace_key(dependencies)
    if st.session_state.get(_key("workspace")) != workspace:
        for key in list(st.session_state):
            if key.startswith(PREFIX):
                del st.session_state[key]
        st.session_state[_key("workspace")] = workspace
    _history_form(dependencies, workspace)
    if dependencies.settings.universe != "live":
        st.caption(
            "Demo / local universe selected. Select the live universe to see downloaded "
            "provider history; local and LIVE namespaces stay separate."
        )
    observations = dependencies.storage.list_observations()
    candidates = sorted(
        {
            r.instrument_id
            for r in observations
            if r.market_family == "equity"
            and r.instrument_id.startswith("LIVE:") == (dependencies.settings.universe == "live")
            and r.timestamp.astimezone(ZoneInfo("Asia/Kolkata")).date() <= HISTORY_END
        }
    )
    _hosted_chart()
    if not candidates:
        scope_results(st.session_state, None)
        st.info(
            "No eligible local equity history through 2020. Use the historical download form "
            "above or Import local OHLC evidence. The bundled 2026 demo is outside this study "
            "and is excluded. No replacement data is generated."
        )
        return
    st.subheader("2 · Study & chart")
    instrument = st.selectbox("Local instrument", candidates, key=_key("instrument"))
    if instrument.startswith("SYNTHETIC:"):
        st.warning("SYNTHETIC QA HISTORY · Interface verification only; not performance evidence.")
    left, right = st.columns(2)
    start = left.date_input(
        "Study start",
        date(2015, 1, 1),
        min_value=date(2000, 1, 1),
        max_value=HISTORY_END,
        key=_key("study_start"),
    )
    end = right.date_input(
        "Study end",
        HISTORY_END,
        min_value=date(2000, 1, 1),
        max_value=HISTORY_END,
        key=_key("study_end"),
    )
    try:
        bars = prepare_history(observations, instrument, start, end)
    except ValueError as error:
        scope_results(st.session_state, None)
        st.info(str(error) + ". Adjust study dates or download history above.")
        return
    rows = ohlc_rows(bars)
    c1, c2, c3 = st.columns(3)
    c1.metric("Observed sessions", f"{len(bars):,}")
    c2.metric("First session", rows[0]["time"])
    c3.metric("Last session", rows[-1]["time"])
    st.caption(
        f"{bars[0].currency} / {bars[0].unit} · Indicators warm up within the selected "
        "study window only. Missing warmup values are omitted. Coverage does not certify gap-free data."
    )
    chosen = st.multiselect(
        "Chart indicators",
        list(INDICATORS),
        default=["SMA 20", "SMA 50", "Volume"],
        key=_key("indicators"),
    )
    series = indicator_series(bars)
    components.html(
        local_chart_html(rows, series, [INDICATORS[x] for x in chosen]), height=720, scrolling=True
    )
    with st.expander("Accessible local price and indicator tables"):
        st.dataframe(rows, hide_index=True, use_container_width=True)
        for label in chosen:
            key = INDICATORS[label]
            keys = (
                ["macd_line", "macd_signal", "macd_histogram"]
                if key == "MACD"
                else ["bollinger20_middle", "bollinger20_upper", "bollinger20_lower"]
                if key == "Bollinger"
                else [key]
            )
            for name in keys:
                if name != "volume":
                    st.write(name)
                    if series[name]:
                        st.dataframe(series[name], hide_index=True, use_container_width=True)
                    else:
                        st.caption("Insufficient warmup observations.")
    st.download_button(
        "Download local OHLC (CSV)",
        csv_text(rows),
        "local-history.csv",
        "text/csv",
        key=_key("ohlc_csv"),
    )
    st.subheader("3 · Backtest")
    st.caption(
        "Long / cash · Close signal → next observed session open · Final position marked to market"
    )
    strategy = st.selectbox("Strategy", list(STRATEGIES), key=_key("strategy"))
    a, b, c = st.columns(3)
    capital = a.number_input(
        f"Initial capital ({bars[0].currency})",
        min_value=1.0,
        max_value=1e12,
        value=100000.0,
        step=1000.0,
        key=_key("capital"),
    )
    cost = b.number_input("Fee per fill (bps)", 0.0, 9999.0, 10.0, key=_key("cost"))
    slip = c.number_input("Slippage per fill (bps)", 0.0, 9999.0, 5.0, key=_key("slippage"))
    fast, slow, buy, sell = 20, 50, 30.0, 70.0
    if STRATEGIES[strategy] in {"sma_cross", "ema_cross"}:
        a, b = st.columns(2)
        fast = a.number_input("Fast period (sessions)", 1, 9999, 20, key=_key("fast"))
        slow = b.number_input("Slow period (sessions)", 2, 10000, 50, key=_key("slow"))
    elif STRATEGIES[strategy] == "rsi_reversion":
        a, b = st.columns(2)
        buy = a.number_input("RSI buy at or below", 0.0, 100.0, 30.0, key=_key("rsi_buy"))
        sell = b.number_input("RSI sell at or above", 0.0, 100.0, 70.0, key=_key("rsi_sell"))
    params = dict(
        strategy=STRATEGIES[strategy],
        initial_capital=capital,
        cost_bps=cost,
        slippage_bps=slip,
        fast_period=fast,
        slow_period=slow,
        rsi_buy=buy,
        rsi_sell=sell,
    )
    scope = fingerprint(
        dict(
            workspace=workspace,
            instrument=instrument,
            start=start.isoformat(),
            end=end.isoformat(),
            params=params,
            bars=[r.model_dump(mode="json") for r in bars],
        )
    )
    scope_results(st.session_state, scope)
    if st.button("Run backtest", type="primary", key=_key("run_backtest")):
        st.session_state.pop(_key("simulation"), None)
        try:
            with st.spinner("Evaluating next-open fills…"):
                result = run_backtest(bars, **params)
            result["manifest"] = result_manifest(bars, params, start, end)
            st.session_state[_key("backtest")] = result
        except ValueError as error:
            st.error(str(error))
    result = st.session_state.get(_key("backtest"))
    if not result:
        st.info("Choose your study and run a backtest to inspect results and enable Monte Carlo.")
        return
    metrics = result["metrics"]
    a, b, c, d = st.columns(4)
    a.metric("Strategy return", _percent(metrics["total_return"]))
    b.metric("Buy & hold return", _percent(metrics["benchmark_return"]))
    c.metric("Max drawdown", _percent(metrics["max_drawdown"]))
    d.metric("Sharpe", "Not available" if metrics["sharpe"] is None else f"{metrics['sharpe']:.2f}")
    import pandas as pd

    st.line_chart(
        pd.DataFrame(result["equity"])
        .set_index("time")
        .rename(columns={"value": "Strategy", "benchmark": "Buy & hold"}),
        use_container_width=True,
    )
    st.caption(
        f"Closed trades: {metrics['closed_trades']} · Win rate: {_percent(metrics['win_rate'])} · "
        f"CAGR: {_percent(metrics['cagr'])}. Equity values in {bars[0].currency}."
    )
    if result.get("open_position"):
        st.info(
            "Position remains open at the study end. Final equity includes its last-close "
            "market value; no forced exit or hypothetical exit fee is applied."
        )
    else:
        st.caption("No open position at study end.")
    with st.expander("Trades, equity values & assumptions"):
        if result["trades"]:
            st.dataframe(result["trades"], hide_index=True, use_container_width=True)
        else:
            st.info(
                "No fills for this study. Warmup and signal thresholds may leave the strategy in cash."
            )
        st.dataframe(result["equity"], hide_index=True, use_container_width=True)
        for assumption in result["assumptions"]:
            st.write("• " + assumption)
    _json_download("Download backtest + manifest (JSON)", result, "backtest.json")
    st.download_button(
        "Download trades (CSV)",
        csv_text(result["trades"]),
        "trades.csv",
        "text/csv",
        key=_key("trades_csv"),
        disabled=not result["trades"],
    )
    _simulation(result, bars, start, end, scope)


def _simulation(backtest, bars, start, end, parent_scope):
    st.subheader("4 · Monte Carlo")
    st.caption(
        "Moving-block bootstrap of strategy equity returns. Resampled scenarios are not "
        "probabilities of future market outcomes. Animation starts paused."
    )
    with st.form(_key("mc_form")):
        a, b, c = st.columns(3)
        paths = a.number_input("Simulated paths", 1, 2000, 300, key=_key("mc_paths"))
        horizon = b.number_input(
            "Horizon (observed sessions)", 1, 2520, 252, key=_key("mc_horizon")
        )
        seed = c.number_input("Random seed", 0, 2**32 - 1, 42, key=_key("mc_seed"))
        block = st.number_input(
            "Block size (returns)",
            1,
            max(1, len(backtest["daily_returns"])),
            min(5, max(1, len(backtest["daily_returns"]))),
            key=_key("mc_block"),
        )
        submitted = st.form_submit_button("Simulate return paths", type="primary")
    params = dict(
        initial_capital=backtest["manifest"]["params"]["initial_capital"],
        simulations=paths,
        horizon=horizon,
        seed=seed,
        block_size=block,
    )
    scope = fingerprint(dict(parent=parent_scope, params=params))
    if st.session_state.get(_key("simulation_scope")) != scope:
        st.session_state.pop(_key("simulation"), None)
        st.session_state[_key("simulation_scope")] = scope
    if submitted:
        try:
            with st.spinner("Resampling historical returns…"):
                result = monte_carlo(backtest["daily_returns"], **params)
            result["manifest"] = result_manifest(
                bars, params, start, end, kind="monte_carlo", parent=backtest["manifest"]
            )
            st.session_state[_key("simulation")] = result
        except ValueError as error:
            st.error(str(error))
    result = st.session_state.get(_key("simulation"))
    if not result:
        return
    reduced = st.checkbox(
        "Prefer reduced motion",
        value=False,
        key=_key("reduced_motion"),
        help="Show complete static paths. System reduced-motion preference is also respected.",
    )
    metrics = result["metrics"]
    a, b, c = st.columns(3)
    a.metric("Resampled loss frequency", _percent(metrics["probability_loss"]))
    b.metric("Median terminal capital", f"{metrics['median_terminal']:,.2f}")
    c.metric("5th percentile terminal", f"{metrics['p05_terminal']:,.2f}")
    st.write(
        f"{paths:,} paths over {horizon:,} observed sessions; terminal p05 / median / p95: "
        f"{metrics['p05_terminal']:,.2f} / {metrics['median_terminal']:,.2f} / "
        f"{metrics['p95_terminal']:,.2f} {bars[0].currency}. "
        "The shaded band contains the central 90% of simulated capital at each step."
    )
    components.html(monte_carlo_html(result, reduced), height=480, scrolling=True)
    with st.expander("Accessible percentile bands & simulation assumptions"):
        st.dataframe(result["bands"], hide_index=True, use_container_width=True)
        for assumption in result["assumptions"]:
            st.write("• " + assumption)
    _json_download("Download Monte Carlo + manifest (JSON)", result, "monte-carlo.json")
