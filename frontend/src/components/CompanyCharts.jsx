import React, { useMemo } from "react";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";
import useChartTheme from "../hooks/useChartTheme";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler);

// Charts for the Company page, styled like StockChart: ink primary line, muted secondary,
// mono gray ticks, surface tooltips, faint gridlines. Colours come from useChartTheme().

const mono = { family: "ui-monospace, SFMono-Regular, Menlo, monospace", size: 10 };

const tooltipOf = (c) => ({
  backgroundColor: c.tooltipBg,
  titleColor: c.tooltipTitle,
  bodyColor: c.tooltipBody,
  borderColor: c.tooltipBorder,
  borderWidth: 1,
  titleFont: { family: "Inter", weight: "500" },
  bodyFont: { family: "Inter" },
  padding: 12,
});

const legendOf = (c) => ({
  position: "top",
  align: "end",
  labels: { color: c.muted, font: mono, usePointStyle: true, pointStyle: "line", boxWidth: 24 },
});

const baseScales = (c, yTick) => ({
  x: {
    grid: { display: false },
    border: { color: c.axis },
    ticks: { color: c.muted, font: mono, maxRotation: 0, autoSkipPadding: 20 },
  },
  y: {
    grid: { color: c.grid },
    border: { display: false },
    ticks: { color: c.muted, font: mono, callback: yTick },
  },
});

const areaFillOf = (rgb) => (context) => {
  const { ctx, chartArea } = context.chart;
  if (!chartArea) return null;
  const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  g.addColorStop(0, `rgba(${rgb}, 0.14)`);
  g.addColorStop(1, `rgba(${rgb}, 0)`);
  return g;
};

const dayKey = (d) => String(d).slice(0, 10);
const shortDate = (d, long) =>
  new Date(d).toLocaleDateString("en-IN", long ? { month: "short", year: "2-digit" } : { day: "2-digit", month: "short" });

// Stock vs benchmark, both rebased to 100 at the first date where both have a close
export function CompareChart({ data, benchmark, name, height = 340 }) {
  const series = useMemo(() => {
    const rows = (data || []).filter((r) => Number(r.close) > 0);
    if (rows.length < 2) return null;

    const bench = new Map((benchmark?.data || []).map((b) => [dayKey(b.date), Number(b.close)]));
    let last = null;
    const benchAligned = rows.map((r) => {
      const v = bench.get(dayKey(r.date));
      if (Number.isFinite(v) && v > 0) last = v;
      return last;
    });

    const start = benchAligned.findIndex((v) => v != null);
    const base = rows[Math.max(0, start)].close;
    const bBase = start >= 0 ? benchAligned[start] : null;
    const spanDays = (new Date(rows[rows.length - 1].date) - new Date(rows[0].date)) / 864e5;

    return {
      labels: rows.map((r) => shortDate(r.date, spanDays > 400)),
      stock: rows.map((r, i) => (i < start ? null : +(r.close / base * 100).toFixed(2))),
      bench: bBase ? benchAligned.map((v, i) => (i < start || v == null ? null : +(v / bBase * 100).toFixed(2))) : [],
      closes: rows.map((r) => r.close),
    };
  }, [data, benchmark]);

  const c = useChartTheme();
  if (!series) return null;
  const tooltip = tooltipOf(c);
  const legend = legendOf(c);

  const chartData = {
    labels: series.labels,
    datasets: [
      {
        label: name || "Stock",
        data: series.stock,
        borderColor: c.line,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        fill: "start",
        backgroundColor: areaFillOf(c.lineRgb),
        spanGaps: true,
      },
      ...(series.bench.length
        ? [{
            label: benchmark?.name || "Benchmark",
            data: series.bench,
            borderColor: c.secondary,
            borderWidth: 1.5,
            borderDash: [5, 4],
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.2,
            spanGaps: true,
          }]
        : []),
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend,
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) => {
            if (ctx.parsed.y == null) return null;
            const extra = ctx.datasetIndex === 0 ? `  (₹${Number(series.closes[ctx.dataIndex]).toLocaleString("en-IN")})` : "";
            return `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}${extra}`;
          },
        },
      },
    },
    scales: baseScales(c, (v) => v),
  };

  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Line data={chartData} options={options} />
    </div>
  );
}

// Quarterly revenue (white) and net profit (gray; red when negative), INR crore
export function QuarterlyChart({ quarterly, height = 300 }) {
  const c = useChartTheme();
  const tooltip = tooltipOf(c);
  const legend = legendOf(c);
  const labels = quarterly.map((q) => shortDate(q.period_end, true));
  const profit = quarterly.map((q) => (q.net_profit == null ? null : Number(q.net_profit)));

  const chartData = {
    labels,
    datasets: [
      {
        label: "Revenue",
        data: quarterly.map((q) => (q.revenue == null ? null : Number(q.revenue))),
        backgroundColor: c.bar,
        borderRadius: 2,
        maxBarThickness: 28,
      },
      {
        label: "Net profit",
        data: profit,
        backgroundColor: profit.map((v) => (v != null && v < 0 ? c.negative : c.bar2)),
        borderRadius: 2,
        maxBarThickness: 28,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { ...legend, labels: { ...legend.labels, pointStyle: "rect", boxWidth: 10 } },
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) => (ctx.parsed.y == null ? null : `${ctx.dataset.label}: ₹${ctx.parsed.y.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr`),
        },
      },
    },
    scales: baseScales(c, (v) => `₹${Number(v).toLocaleString("en-IN")}`),
  };

  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Bar data={chartData} options={options} />
    </div>
  );
}

// Growth score over snapshots
export function ScoreHistoryChart({ history, height = 160 }) {
  const c = useChartTheme();
  const tooltip = tooltipOf(c);
  const chartData = {
    labels: history.map((h) => shortDate(h.snapshot_date)),
    datasets: [{
      label: "Growth score",
      data: history.map((h) => (h.growth_score == null ? null : Number(h.growth_score))),
      borderColor: c.line,
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: c.line,
      tension: 0.2,
      spanGaps: true,
    }],
  };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) => {
            const h = history[ctx.dataIndex];
            return `Score ${ctx.parsed.y?.toFixed(1) ?? "—"}${h.rank_overall ? ` · #${h.rank_overall}` : ""}`;
          },
        },
      },
    },
    scales: { ...baseScales(c, (v) => v), y: { ...baseScales(c, (v) => v).y, min: 0, max: 100 } },
  };
  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
