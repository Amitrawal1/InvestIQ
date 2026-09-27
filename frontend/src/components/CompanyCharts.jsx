import React, { useMemo } from "react";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler);

// Charts for the Company page, styled like StockChart: white primary line, muted secondary,
// mono gray ticks, #0a0a0a tooltips, faint gridlines.

const WHITE = "#f5f5f5";
const GRAY = "#6b7280";
const MUTED = "#9ca3af";
const mono = { family: "ui-monospace, SFMono-Regular, Menlo, monospace", size: 10 };

const tooltip = {
  backgroundColor: "#0a0a0a",
  titleColor: "#fff",
  bodyColor: "#d1d5db",
  borderColor: "#1f2937",
  borderWidth: 1,
  titleFont: { family: "Inter", weight: "500" },
  bodyFont: { family: "Inter" },
  padding: 12,
};

const legend = {
  position: "top",
  align: "end",
  labels: { color: MUTED, font: mono, usePointStyle: true, pointStyle: "line", boxWidth: 24 },
};

const baseScales = (yTick) => ({
  x: {
    grid: { display: false },
    border: { color: "#1f2937" },
    ticks: { color: MUTED, font: mono, maxRotation: 0, autoSkipPadding: 20 },
  },
  y: {
    grid: { color: "rgba(255, 255, 255, 0.05)" },
    border: { display: false },
    ticks: { color: MUTED, font: mono, callback: yTick },
  },
});

const areaFill = (context) => {
  const { ctx, chartArea } = context.chart;
  if (!chartArea) return null;
  const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  g.addColorStop(0, "rgba(245, 245, 245, 0.14)");
  g.addColorStop(1, "rgba(245, 245, 245, 0)");
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

  if (!series) return null;

  const chartData = {
    labels: series.labels,
    datasets: [
      {
        label: name || "Stock",
        data: series.stock,
        borderColor: WHITE,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        fill: "start",
        backgroundColor: areaFill,
        spanGaps: true,
      },
      ...(series.bench.length
        ? [{
            label: benchmark?.name || "Benchmark",
            data: series.bench,
            borderColor: GRAY,
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
    scales: baseScales((v) => v),
  };

  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Line data={chartData} options={options} />
    </div>
  );
}

// Quarterly revenue (white) and net profit (gray; red when negative), INR crore
export function QuarterlyChart({ quarterly, height = 300 }) {
  const labels = quarterly.map((q) => shortDate(q.period_end, true));
  const profit = quarterly.map((q) => (q.net_profit == null ? null : Number(q.net_profit)));

  const chartData = {
    labels,
    datasets: [
      {
        label: "Revenue",
        data: quarterly.map((q) => (q.revenue == null ? null : Number(q.revenue))),
        backgroundColor: "rgba(245, 245, 245, 0.85)",
        borderRadius: 2,
        maxBarThickness: 28,
      },
      {
        label: "Net profit",
        data: profit,
        backgroundColor: profit.map((v) => (v != null && v < 0 ? "rgba(248, 113, 113, 0.8)" : "rgba(107, 114, 128, 0.9)")),
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
    scales: baseScales((v) => `₹${Number(v).toLocaleString("en-IN")}`),
  };

  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Bar data={chartData} options={options} />
    </div>
  );
}

// Growth score over snapshots
export function ScoreHistoryChart({ history, height = 160 }) {
  const chartData = {
    labels: history.map((h) => shortDate(h.snapshot_date)),
    datasets: [{
      label: "Growth score",
      data: history.map((h) => (h.growth_score == null ? null : Number(h.growth_score))),
      borderColor: WHITE,
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: WHITE,
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
    scales: { ...baseScales((v) => v), y: { ...baseScales((v) => v).y, min: 0, max: 100 } },
  };
  return (
    <div style={{ height, position: "relative", width: "100%" }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
