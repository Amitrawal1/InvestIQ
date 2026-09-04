import React, { useRef, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const StockChart = ({ ticker, historicalData, predictions }) => {
  const chartRef = useRef(null);

  // Generate labels and datasets
  const historyCount = historicalData ? historicalData.length : 15;
  const labels = [];
  const historyPrices = [];
  const predictionPrices = [];

  // Generate Mock historical data if not provided
  if (!historicalData || historicalData.length === 0) {
    const basePrice = ticker === 'RELIANCE' ? 2450 : ticker === 'TCS' ? 3850 : ticker === 'INFY' ? 1420 : ticker === 'HDFCBANK' ? 1550 : 500;
    for (let i = 15; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      labels.push(d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));
      
      // Simulate random walk
      const fluctuation = (Math.random() - 0.45) * (basePrice * 0.015);
      const price = parseFloat((basePrice + (15 - i) * (basePrice * 0.002) + fluctuation).toFixed(2));
      historyPrices.push(price);
      predictionPrices.push(null); // No prediction for historical dates
    }
  } else {
    historicalData.forEach(item => {
      labels.push(new Date(item.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));
      historyPrices.push(item.close);
      predictionPrices.push(null);
    });
  }

  // Setup predictive part
  const lastHistoricalPrice = historyPrices[historyPrices.length - 1];
  predictionPrices[predictionPrices.length - 1] = lastHistoricalPrice; // Anchor prediction to last historical point

  const predCount = predictions ? predictions.length : 5;
  if (!predictions || predictions.length === 0) {
    // Generate simulated forecast walk
    let currentPred = lastHistoricalPrice;
    const trendDir = ticker === 'RELIANCE' ? 1.008 : ticker === 'TCS' ? 1.005 : ticker === 'INFY' ? 0.992 : 1.002; // Reliance/TCS bullish, Infy slightly bearish
    
    for (let i = 1; i <= predCount; i++) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      labels.push(d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ' (F)');
      
      const nextVal = currentPred * trendDir + (Math.random() - 0.5) * (currentPred * 0.01);
      currentPred = parseFloat(nextVal.toFixed(2));
      predictionPrices.push(currentPred);
      historyPrices.push(null); // No historical price here
    }
  } else {
    predictions.forEach((val, index) => {
      const d = new Date();
      d.setDate(d.getDate() + index + 1);
      labels.push(d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ' (F)');
      predictionPrices.push(val);
      historyPrices.push(null);
    });
  }

  const data = {
    labels,
    datasets: [
      {
        label: 'Historical Close Price (INR)',
        data: historyPrices,
        borderColor: '#00f2fe',
        borderWidth: 3,
        pointBackgroundColor: '#00f2fe',
        pointHoverRadius: 7,
        tension: 0.2,
        spanGaps: true,
        fill: 'start',
        backgroundColor: (context) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return null;
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(0, 242, 254, 0.25)');
          gradient.addColorStop(1, 'rgba(0, 242, 254, 0.0)');
          return gradient;
        }
      },
      {
        label: 'AI Forecasted Trend (INR)',
        data: predictionPrices,
        borderColor: '#8a2be2',
        borderWidth: 3,
        borderDash: [5, 5],
        pointBackgroundColor: '#8a2be2',
        pointHoverRadius: 7,
        tension: 0.2,
        spanGaps: true,
        fill: 'start',
        backgroundColor: (context) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return null;
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(138, 43, 226, 0.25)');
          gradient.addColorStop(1, 'rgba(138, 43, 226, 0.0)');
          return gradient;
        }
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#90a0c7',
          font: {
            family: 'Outfit',
            size: 12
          }
        }
      },
      tooltip: {
        backgroundColor: 'rgba(13, 20, 35, 0.95)',
        titleColor: '#fff',
        bodyColor: '#90a0c7',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        titleFont: {
          family: 'Outfit',
          weight: 'bold'
        },
        bodyFont: {
          family: 'Inter'
        },
        padding: 12,
        displayColors: true
      }
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.03)'
        },
        ticks: {
          color: '#90a0c7',
          font: {
            family: 'Inter',
            size: 11
          }
        }
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.03)'
        },
        ticks: {
          color: '#90a0c7',
          font: {
            family: 'Inter',
            size: 11
          },
          callback: function(value) {
            return '₹' + value.toLocaleString('en-IN');
          }
        }
      }
    }
  };

  return (
    <div style={{ height: '350px', position: 'relative', width: '100%' }}>
      <Line ref={chartRef} data={data} options={options} />
    </div>
  );
};

export default StockChart;
