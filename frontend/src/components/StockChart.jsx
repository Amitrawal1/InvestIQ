import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import useChartTheme from '../hooks/useChartTheme';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

const fmtDate = (d) => d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });

// Build history + forecast series. Falls back to a simulated walk when no data is passed.
function buildSeries(ticker, historicalData, predictions) {
  const labels = [];
  const historyPrices = [];
  const predictionPrices = [];

  if (!historicalData || historicalData.length === 0) {
    const basePrice = ticker === 'RELIANCE' ? 2450 : ticker === 'TCS' ? 3850 : ticker === 'INFY' ? 1420 : ticker === 'HDFCBANK' ? 1550 : 500;
    for (let i = 15; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      labels.push(fmtDate(d));

      const fluctuation = (Math.random() - 0.45) * (basePrice * 0.015);
      historyPrices.push(parseFloat((basePrice + (15 - i) * (basePrice * 0.002) + fluctuation).toFixed(2)));
      predictionPrices.push(null);
    }
  } else {
    historicalData.forEach(item => {
      labels.push(fmtDate(new Date(item.date)));
      historyPrices.push(item.close);
      predictionPrices.push(null);
    });
  }

  // Anchor the forecast line to the last historical point
  const lastHistoricalPrice = historyPrices[historyPrices.length - 1];
  predictionPrices[predictionPrices.length - 1] = lastHistoricalPrice;

  const forecast = predictions && predictions.length > 0 ? predictions : null;

  if (!forecast) {
    let currentPred = lastHistoricalPrice;
    const trendDir = ticker === 'RELIANCE' ? 1.008 : ticker === 'TCS' ? 1.005 : ticker === 'INFY' ? 0.992 : 1.002;

    for (let i = 1; i <= 5; i++) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      labels.push(fmtDate(d) + ' (F)');

      currentPred = parseFloat((currentPred * trendDir + (Math.random() - 0.5) * (currentPred * 0.01)).toFixed(2));
      predictionPrices.push(currentPred);
      historyPrices.push(null);
    }
  } else {
    forecast.forEach((val, index) => {
      const d = new Date();
      d.setDate(d.getDate() + index + 1);
      labels.push(fmtDate(d) + ' (F)');
      predictionPrices.push(val);
      historyPrices.push(null);
    });
  }

  return { labels, historyPrices, predictionPrices };
}

const areaFill = (rgb) => (context) => {
  const { ctx, chartArea } = context.chart;
  if (!chartArea) return null;
  const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
  gradient.addColorStop(0, `rgba(${rgb}, 0.18)`);
  gradient.addColorStop(1, `rgba(${rgb}, 0)`);
  return gradient;
};

const StockChart = ({ ticker, historicalData, predictions, height = 350 }) => {
  // Memoised so unrelated re-renders (e.g. typing in search) don't regenerate the series
  const { labels, historyPrices, predictionPrices } = useMemo(
    () => buildSeries(ticker, historicalData, predictions),
    [ticker, historicalData, predictions]
  );

  // Colours come from the theme tokens (--chart-*, --accent); the forecast uses the Intro globe accent
  const c = useChartTheme();
  const HISTORY_COLOR = c.line;
  const FORECAST_COLOR = c.accent;
  const MUTED = c.muted;

  const data = {
    labels,
    datasets: [
      {
        label: 'Close price',
        data: historyPrices,
        borderColor: HISTORY_COLOR,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: HISTORY_COLOR,
        tension: 0.25,
        spanGaps: true,
        fill: 'start',
        backgroundColor: areaFill(c.lineRgb),
      },
      {
        label: 'AI forecast',
        data: predictionPrices,
        borderColor: FORECAST_COLOR,
        borderWidth: 2,
        borderDash: [6, 5],
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: FORECAST_COLOR,
        tension: 0.25,
        spanGaps: true,
        fill: 'start',
        backgroundColor: areaFill(c.accentRgb),
      }
    ]
  };

  const mono = { family: 'ui-monospace, SFMono-Regular, Menlo, monospace', size: 10 };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: {
          color: MUTED,
          font: mono,
          usePointStyle: true,
          pointStyle: 'line',
          boxWidth: 24,
        }
      },
      tooltip: {
        backgroundColor: c.tooltipBg,
        titleColor: c.tooltipTitle,
        bodyColor: c.tooltipBody,
        borderColor: c.tooltipBorder,
        borderWidth: 1,
        titleFont: { family: 'Inter', weight: '500' },
        bodyFont: { family: 'Inter' },
        padding: 12,
        callbacks: {
          label: (ctx) => ctx.parsed.y == null
            ? null
            : `${ctx.dataset.label}: ₹${ctx.parsed.y.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        border: { color: c.axis },
        ticks: { color: MUTED, font: mono, maxRotation: 0, autoSkipPadding: 16 }
      },
      y: {
        grid: { color: c.grid },
        border: { display: false },
        ticks: {
          color: MUTED,
          font: mono,
          callback: (value) => '₹' + value.toLocaleString('en-IN')
        }
      }
    }
  };

  return (
    <div style={{ height, position: 'relative', width: '100%' }}>
      <Line data={data} options={options} />
    </div>
  );
};

export default StockChart;
