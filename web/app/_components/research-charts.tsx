"use client";

// Chart components built on lightweight-charts: PriceChart (OHLC + indicator panes) and EquityChart
// (strategy vs buy & hold). Data comes from the strategy-lab and technicals API responses.
import { useEffect, useRef, useState } from "react";
import type { IChartApi, Time } from "lightweight-charts";
import type { Backtest, Bar, Point } from "./types";
import { format } from "./types";
import { useTheme } from "./theme-toggle";

const NO_INDICATORS: Record<string, Point[]> = {};
const NO_SELECTION: string[] = [];
function chartPalette() {
  const styles = getComputedStyle(document.documentElement);
  const color = (token: string) => styles.getPropertyValue(token).trim();
  return { background: color("--chart-bg"), text: color("--chart-text"), grid: color("--chart-grid"), up: color("--chart-up"), down: color("--chart-down"), volume: color("--chart-volume"), lines: [color("--chart-gold"), color("--chart-up"), color("--mode-text"), color("--chart-secondary"), color("--chart-down"), color("--chart-volume")] };
}
const GROUPS: Record<string, string[]> = {
  macd: ["macd_line", "macd_signal", "macd_histogram"],
  bollinger: ["bollinger20_middle", "bollinger20_upper", "bollinger20_lower"],
};

function Attribution() {
  return <div className="chart-caption"><span>Local observations · drag to pan, scroll to zoom · tables available below</span><a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView Lightweight Charts™ · Copyright (с) 2025 TradingView, Inc.</a></div>;
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
  useEffect(() => {
    if (!container.current || !bars.length) return;
    let disposed = false;
    let chart: IChartApi | undefined;
    import("lightweight-charts").then(L => {
      if (disposed || !container.current) return;
      const palette = chartPalette();
      chart = L.createChart(container.current, options(palette));
      chart.addSeries(L.CandlestickSeries, { upColor: palette.up, downColor: palette.down, borderVisible: false, wickUpColor: palette.up, wickDownColor: palette.down }).setData(bars.map(bar => ({ ...bar, time: bar.time as Time })));
      let pane = 0, color = 0;
      for (const selection of selected) {
        const key = selection.toLowerCase();
        if (key === "volume") {
          chart.addSeries(L.HistogramSeries, { title: "Volume", color: palette.volume, priceFormat: { type: "volume" } }, ++pane)
            .setData(bars.map(bar => ({ time: bar.time as Time, value: bar.volume })));
          continue;
        }
        const names = GROUPS[key] || [key];
        const paneIndex = /^(rsi|macd|atr|adx)/.test(key) ? ++pane : 0;
        for (const name of names) {
          const points = indicators[name] || [];
          if (!points.length) continue;
          const series = chart.addSeries(name === "macd_histogram" ? L.HistogramSeries : L.LineSeries, {
            title: name.replaceAll("_", " "), color: palette.lines[color++ % palette.lines.length],
            priceLineVisible: false, lastValueVisible: false,
          }, paneIndex);
          series.setData(points.map(point => ({ ...point, time: point.time as Time })));
        }
      }
      chart.panes().forEach((item, index) => item.setHeight(index === 0 ? 310 : 100));
      chart.timeScale().fitContent();
      setError("");
    }).catch(() => { if (!disposed) setError("Interactive chart unavailable. Exact local values remain available in the table below."); });
    return () => { disposed = true; chart?.remove(); };
  }, [bars, indicators, selected, theme]);

  if (!bars.length) return <p className="muted">No observed sessions to chart.</p>;
  return <>
    {error && <p className="alert warning" role="status">{error}</p>}
    <div className="chart-frame" ref={container} role="img" aria-label={`Historical OHLC chart, ${bars.length} observed sessions, ${bars[0].time} through ${bars.at(-1)?.time}. ${selected.join(", ") || "Price only"}.`} />
    <Attribution />
    <details className="json-view"><summary>Accessible price and indicator data ({bars.length} sessions)</summary>
      <div className="table-scroll"><table><caption className="sr-only">Local OHLC and volume, without calendar filling</caption><thead><tr>{["Session", "Open", "High", "Low", "Close", "Volume"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{bars.map(bar => <tr key={bar.time}><th scope="row">{bar.time}</th>{[bar.open, bar.high, bar.low, bar.close, bar.volume].map((value, index) => <td className="numeric" key={index}>{format(value)}</td>)}</tr>)}</tbody></table></div>
      {selected.flatMap(key => GROUPS[key.toLowerCase()] || [key.toLowerCase()]).filter(key => key !== "volume").map(key => <details key={key}><summary>{key.replaceAll("_", " ")}</summary>{indicators[key]?.length ? <div className="table-scroll"><table><thead><tr><th scope="col">Session</th><th scope="col">Value</th></tr></thead><tbody>{indicators[key].map(point => <tr key={point.time}><th scope="row">{point.time}</th><td className="numeric">{format(point.value, 4)}</td></tr>)}</tbody></table></div> : <p className="muted">Insufficient warmup observations.</p>}</details>)}
    </details>
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
  return <>{error && <p className="alert warning" role="status">{error}</p>}<div ref={container} className="chart-frame" role="img" aria-label="Strategy equity (solid line) and cost-matched buy and hold (dashed line)" /><Attribution /><details className="json-view"><summary>Accessible equity values</summary><div className="table-scroll"><table><thead><tr><th scope="col">Session</th><th scope="col">Strategy</th><th scope="col">Buy & hold</th></tr></thead><tbody>{points.map(point => <tr key={point.time}><th scope="row">{point.time}</th><td className="numeric">{format(point.value)}</td><td className="numeric">{format(point.benchmark)}</td></tr>)}</tbody></table></div></details></>;
}
