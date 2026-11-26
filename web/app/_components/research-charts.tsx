"use client";

// Chart components built on lightweight-charts: PriceChart (OHLC + indicator panes) and EquityChart
// (strategy vs buy & hold). Data comes from the strategy-lab and technicals API responses. Also the opt-in
// TradingView widget (HostedChart).
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { IChartApi, Time } from "lightweight-charts";
import type { Backtest, Bar, Point } from "./types";
import { format } from "./types";
import { useTheme } from "./theme-toggle";

const NO_INDICATORS: Record<string, Point[]> = {};
const NO_SELECTION: string[] = [];
const LINE_TOKENS = ["--chart-gold", "--chart-up", "--mode-text", "--chart-secondary", "--chart-down", "--chart-volume", "--mode-link"];
const SERIES_COLORS: Record<string, number> = {
  sma20: 0, sma50: 1, sma200: 2, ema20: 3, ema50: 4,
  bollinger20_middle: 0, bollinger20_upper: 5, bollinger20_lower: 6,
  macd_line: 6, macd_signal: 0, macd_histogram: 5, rsi14: 6, atr14: 0, adx14: 3, volume: 5,
};
function chartPalette() {
  const styles = getComputedStyle(document.documentElement);
  const color = (token: string) => styles.getPropertyValue(token).trim();
  return { background: color("--chart-bg"), text: color("--chart-text"), grid: color("--chart-grid"), up: color("--chart-up"), down: color("--chart-down"), volume: color("--chart-volume"), lines: LINE_TOKENS.map(color) };
}
const GROUPS: Record<string, string[]> = {
  macd: ["macd_line", "macd_signal", "macd_histogram"],
  bollinger: ["bollinger20_middle", "bollinger20_upper", "bollinger20_lower"],
};
const indicatorLabel = (name: string) => {
  const [indicator, part] = name.split("_");
  if (indicator === "bollinger20") return `Bollinger ${part}`;
  if (indicator === "volume") return "Volume";
  return indicator.toUpperCase().replace(/(\d+)$/, " $1") + (part ? ` ${part}` : "");
};

function Attribution() {
  return <div className="chart-caption"><span>Saved prices · drag to pan, scroll to zoom · table below</span><a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView Lightweight Charts™ · Copyright (с) 2025 TradingView, Inc.</a></div>;
}

function ChartData({ label, className, children }: { label: string; className?: string; children: () => ReactNode }) {
  const [opened, setOpened] = useState(false);
  return <details className={className} onToggle={event => { if (event.currentTarget.open) setOpened(true); }}>
    <summary>{label}</summary>
    {opened ? children() : null}
  </details>;
}

const options = (palette: ReturnType<typeof chartPalette>) => ({
  autoSize: true,
  layout: { background: { color: palette.background }, textColor: palette.text, attributionLogo: true },
  grid: { vertLines: { visible: false }, horzLines: { color: palette.grid, style: 1 } },
  rightPriceScale: { borderColor: palette.grid },
  timeScale: { borderColor: palette.grid, timeVisible: false },
});

export function PriceChart({ bars, indicators = NO_INDICATORS, selected = NO_SELECTION }: {
  bars: Bar[]; indicators?: Record<string, Point[]>; selected?: string[];
}) {
  const theme = useTheme();
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const { series, paneCount } = useMemo(() => {
    let paneCount = 0;
    const series = selected.flatMap(selection => {
      const key = selection.toLowerCase();
      const names = key === "volume" ? [key] : (GROUPS[key] || [key]).filter(name => indicators[name]?.length);
      if (!names.length) return [];
      const pane = /^(rsi|macd|atr|adx|volume)/.test(key) ? ++paneCount : 0;
      return names.map(name => ({ name, pane, colorIndex: SERIES_COLORS[name] ?? 0, dashed: name === "bollinger20_middle" }));
    });
    return { series, paneCount };
  }, [indicators, selected]);
  useEffect(() => {
    if (!container.current || !bars.length) return;
    let disposed = false;
    let chart: IChartApi | undefined;
    import("lightweight-charts").then(L => {
      if (disposed || !container.current) return;
      const palette = chartPalette();
      chart = L.createChart(container.current, options(palette));
      chart.addSeries(L.CandlestickSeries, { upColor: palette.up, downColor: palette.down, borderVisible: false, wickUpColor: palette.up, wickDownColor: palette.down }).setData(bars.map(bar => ({ ...bar, time: bar.time as Time })));
      for (const { name, pane, colorIndex, dashed } of series) {
        if (name === "volume") {
          chart.addSeries(L.HistogramSeries, { title: "Volume", color: palette.volume, priceFormat: { type: "volume" } }, pane)
            .setData(bars.map(bar => ({ time: bar.time as Time, value: bar.volume })));
          continue;
        }
        const plotted = chart.addSeries(name === "macd_histogram" ? L.HistogramSeries : L.LineSeries, {
          title: indicatorLabel(name), color: palette.lines[colorIndex], lineStyle: dashed ? L.LineStyle.Dashed : L.LineStyle.Solid,
          priceLineVisible: false, lastValueVisible: false,
        }, pane);
        plotted.setData(indicators[name].map(point => ({ ...point, time: point.time as Time })));
      }
      if (paneCount) chart.panes()[0].setStretchFactor(3);
      chart.timeScale().fitContent();
      setError("");
    }).catch(() => { if (!disposed) setError("Interactive chart unavailable. Exact local values remain available in the table below."); });
    return () => { disposed = true; chart?.remove(); };
  }, [bars, indicators, paneCount, series, theme]);

  if (!bars.length) return <p className="muted">No observed sessions to chart.</p>;
  return <>
    {error && <p className="alert warning" role="status">{error}</p>}
    <div className="chart-frame" ref={container} role="img" style={paneCount ? { height: 340 + 100 * paneCount } : undefined} aria-label={`Historical OHLC chart, ${bars.length} observed sessions, ${bars[0].time} through ${bars.at(-1)?.time}. ${series.map(({ name }) => indicatorLabel(name)).join(", ") || "Price only"}.`} />
    {series.length > 0 && <ul className="chart-legend" aria-label="Plotted indicators">{series.map(({ name, colorIndex, dashed }) => <li key={name}><i aria-hidden="true" style={{ borderTop: `2px ${dashed ? "dashed" : "solid"} var(${LINE_TOKENS[colorIndex]})` }} />{indicatorLabel(name)}</li>)}</ul>}
    <Attribution />
    <ChartData className="fold" label={`Price and indicator data as a table (${bars.length} sessions)`}>{() => <>
      <div className="table-scroll"><table><caption className="sr-only">Local OHLC and volume, without calendar filling</caption><thead><tr>{["Session", "Open", "High", "Low", "Close", "Volume"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{bars.map(bar => <tr key={bar.time}><th scope="row">{bar.time}</th>{[bar.open, bar.high, bar.low, bar.close, bar.volume].map((value, index) => <td className="numeric" key={index}>{format(value)}</td>)}</tr>)}</tbody></table></div>
      {selected.flatMap(key => GROUPS[key.toLowerCase()] || [key.toLowerCase()]).filter(key => key !== "volume").map(key => <ChartData key={key} label={indicatorLabel(key)}>{() => indicators[key]?.length ? <div className="table-scroll"><table><thead><tr><th scope="col">Session</th><th scope="col">Value</th></tr></thead><tbody>{indicators[key].map(point => <tr key={point.time}><th scope="row">{point.time}</th><td className="numeric">{format(point.value, 4)}</td></tr>)}</tbody></table></div> : <p className="muted">Insufficient warm-up observations.</p>}</ChartData>)}
    </>}</ChartData>
  </>;
}

export function EquityChart({ points }: { points: Backtest["equity"] }) {
  const theme = useTheme();
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!container.current || !points.length) return;
    let disposed = false;
    let chart: IChartApi | undefined;
    import("lightweight-charts").then(L => {
      if (disposed || !container.current) return;
      const palette = chartPalette();
      chart = L.createChart(container.current, options(palette));
      chart.addSeries(L.LineSeries, { title: "Strategy", color: palette.lines[0], lineWidth: 2 }).setData(points.map(point => ({ time: point.time as Time, value: point.value })));
      chart.addSeries(L.LineSeries, { title: "Buy & hold", color: palette.lines[1], lineWidth: 2, lineStyle: L.LineStyle.Dashed }).setData(points.map(point => ({ time: point.time as Time, value: point.benchmark })));
      chart.timeScale().fitContent();
      setError("");
    }).catch(() => { if (!disposed) setError("Interactive equity chart unavailable. Use the equity table or JSON report."); });
    return () => { disposed = true; chart?.remove(); };
  }, [points, theme]);
  return <>{error && <p className="alert warning" role="status">{error}</p>}<div ref={container} className="chart-frame" role="img" aria-label="Strategy equity (solid line) and cost-matched buy and hold (dashed line)" /><Attribution /><details className="fold"><summary>Equity values as a table</summary><div className="table-scroll"><table><thead><tr><th scope="col">Session</th><th scope="col">Strategy</th><th scope="col">Buy & hold</th></tr></thead><tbody>{points.map(point => <tr key={point.time}><th scope="row">{point.time}</th><td className="numeric">{format(point.value)}</td><td className="numeric">{format(point.benchmark)}</td></tr>)}</tbody></table></div></details></>;
}

/** Optional TradingView hosted widget (Lab › Indicators). Off until the user opts in; it never feeds local research. */
export function HostedChart({ initialSymbol = "NSE:RELIANCE", interval = "D" }: { initialSymbol?: string; interval?: "D" | "1" }) {
  const theme = useTheme();
  const [enabled, setEnabled] = useState(false), [symbol, setSymbol] = useState(initialSymbol);
  const valid = /^[A-Za-z0-9_:-]{1,80}$/.test(symbol);
  const config = JSON.stringify({ autosize: true, symbol, interval, timezone: "Asia/Kolkata", theme, style: "1", locale: "en", allow_symbol_change: true });
  const light = theme === "light";
  const html = `<html><head><style>html,body{height:100%;margin:0}.tradingview-widget-container{height:480px!important;min-height:480px}</style></head><body style="margin:0;background:${light ? "#ffffff" : "#161a21"};color:${light ? "#111827" : "#e8eaed"}"><div class="tradingview-widget-container" style="height:480px;width:100%"><div class="tradingview-widget-container__widget" style="height:450px;width:100%"></div><a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer" style="color:${light ? "#2f55d4" : "#7b97f0"}">Chart by TradingView</a><script src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>${valid ? config : "{}"}</script></div></body></html>`;
  return <details className="card fold"><summary>TradingView chart (optional, external service)</summary>
    <p className="muted">Data from TradingView may go beyond 2020. It never feeds the local charts, backtests or Monte Carlo. Turning it on sends requests to TradingView.</p>
    <label className="check-label"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Load the TradingView widget</label>
    {enabled && <><label className="field">TradingView exchange:ticker<input value={symbol} onChange={event => setSymbol(event.target.value)} maxLength={80} /></label>{valid ? <iframe title="Independent TradingView hosted chart" className="external-chart" sandbox="allow-scripts allow-popups" srcDoc={html} /> : <p className="field-error">Use exchange:ticker with letters, digits, colon, hyphen or underscore.</p>}<p className="muted small">If TradingView is blocked or unavailable, everything else keeps working.</p></>}
  </details>;
}
