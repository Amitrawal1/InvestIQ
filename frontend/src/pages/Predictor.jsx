import React, { useState } from 'react';
import axios from 'axios';
import { AnimatePresence, motion } from 'motion/react';
import { Calendar, Cpu, Sparkles } from 'lucide-react';
import Navbar from '../components/Navbar';
import StockChart from '../components/StockChart';
import { PageHeading, MonoLabel, Panel, PrimaryButton, Pill } from '../components/ui';

const securities = [
  { value: 'RELIANCE', label: 'Reliance Industries' },
  { value: 'TCS', label: 'Tata Consultancy Services' },
  { value: 'INFY', label: 'Infosys Limited' },
  { value: 'HDFCBANK', label: 'HDFC Bank' },
];

const horizons = [3, 5, 7];

const Predictor = () => {
  const [ticker, setTicker] = useState('RELIANCE');
  const [days, setDays] = useState(5);
  const [loading, setLoading] = useState(false);
  const [forecastResults, setForecastResults] = useState(null);
  const [simulated, setSimulated] = useState(false);

  const triggerInference = async () => {
    setLoading(true);
    setForecastResults(null);
    setSimulated(false);

    try {
      // Direct call to Express which proxies to the model service
      const response = await axios.post('/api/ai/predict', { ticker, days });
      setForecastResults(response.data);
    } catch (err) {
      console.warn('Prediction API offline, using simulated sandbox inference.', err);
      await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate computational load

      const basePrice = ticker === 'RELIANCE' ? 2460.50 : ticker === 'TCS' ? 3855.20 : ticker === 'INFY' ? 1412.10 : 1548.80;
      const trend = ticker === 'RELIANCE' || ticker === 'TCS' ? 0.008 : ticker === 'INFY' ? -0.005 : 0.003;

      const predictionsList = [];
      let currentVal = basePrice;
      for (let i = 1; i <= days; i++) {
        const date = new Date();
        date.setDate(date.getDate() + i);

        // Random walk with predefined drift
        const fluctuation = (Math.random() - 0.48) * (currentVal * 0.015);
        currentVal = parseFloat((currentVal * (1 + trend) + fluctuation).toFixed(2));

        predictionsList.push({
          day: i,
          date: date.toLocaleDateString('en-IN', { weekday: 'long', day: '2-digit', month: 'short' }),
          predicted_price: currentVal,
          direction: fluctuation >= 0 ? 'BULLISH' : 'BEARISH',
          confidence: parseFloat((85 + Math.random() * 12).toFixed(1))
        });
      }

      setSimulated(true);
      setForecastResults({
        ticker,
        model_version: "sandbox-simulation",
        average_confidence: parseFloat((85 + Math.random() * 10).toFixed(1)),
        rsi_metric: parseFloat((45 + Math.random() * 30).toFixed(2)),
        predictions: predictionsList
      });
    } finally {
      setLoading(false);
    }
  };

  const selectClass =
    "w-full appearance-none bg-transparent border-b border-gray-700 pb-3 text-white text-[15px] outline-none focus:border-white transition-colors cursor-pointer [&>option]:bg-[#0a0a0a]";

  return (
    <div className="min-h-screen w-full bg-[#050011] text-white font-sans">
      <Navbar />

      <div className="px-6 md:px-16 pt-12 md:pt-16 pb-12">
        <PageHeading index="03" label="Deep analytics" title="AI FORECAST">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed lg:text-right">
            Pick a security and a horizon.<br className="hidden lg:block" /> The model estimates the next move.
          </p>
        </PageHeading>
      </div>

      <section className="w-full flex flex-col lg:flex-row border-y border-gray-800 bg-[#0a0a0a]">
        {/* SETTINGS */}
        <div className="w-full lg:w-[35%] border-b lg:border-b-0 lg:border-r border-gray-800 flex flex-col">
          <div className="border-b border-gray-800 px-6 md:px-8 py-5 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
            <span className="flex items-center gap-2"><Cpu size={13} /> Inference settings</span>
            <span>01</span>
          </div>

          <div className="px-6 md:px-8 py-8 flex flex-col gap-10">
            <label className="block">
              <span className="block text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-2">Equity security</span>
              <select value={ticker} onChange={(e) => setTicker(e.target.value)} className={selectClass}>
                {securities.map(s => (
                  <option key={s.value} value={s.value}>{s.value} — {s.label}</option>
                ))}
              </select>
            </label>

            <div>
              <span className="block text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-3">Forecast horizon</span>
              <div className="flex flex-wrap gap-2">
                {horizons.map(h => (
                  <Pill key={h} active={days === h} onClick={() => setDays(h)}>
                    {h} days
                  </Pill>
                ))}
              </div>
            </div>

            <Panel className="p-5 bg-white/[0.02]">
              <MonoLabel className="block mb-3 text-white">Active model</MonoLabel>
              <ul className="space-y-2 text-[12px] text-gray-400">
                <li>Model: XGBoost baseline (in development)</li>
                <li>Features: returns, moving averages, volatility, volume, fundamentals</li>
                <li>Data: Upstox prices + financial statements</li>
              </ul>
            </Panel>

            <PrimaryButton onClick={triggerInference} disabled={loading} icon={Sparkles} className="w-full">
              {loading ? 'Running inference…' : 'Run inference'}
            </PrimaryButton>
          </div>
        </div>

        {/* RESULTS */}
        <div className="w-full lg:w-[65%] flex flex-col min-h-[520px]">
          <div className="border-b border-gray-800 px-6 md:px-8 py-5 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
            <span>Inference outputs</span>
            <span>{forecastResults ? forecastResults.ticker : '02'}</span>
          </div>

          <AnimatePresence mode="wait">
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-1 flex-col items-center justify-center gap-6 px-8 py-16 text-center"
              >
                <div className="h-12 w-12 animate-spin rounded-full border-2 border-gray-800 border-t-[#d942ff]" />
                <div>
                  <p className="text-lg font-medium tracking-tight">Connecting to the AI engine…</p>
                  <p className="mt-2 text-[10px] font-mono tracking-widest uppercase text-gray-500">
                    Computing features and scoring the model
                  </p>
                </div>
              </motion.div>
            )}

            {!loading && !forecastResults && (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-1 flex-col items-center justify-center px-8 py-16 text-center"
              >
                <span className="text-gray-600 text-xl tracking-[0.3em] mb-6">***</span>
                <h3 className="text-2xl md:text-[2rem] font-medium tracking-tight text-[#555]">No active inference</h3>
                <p className="mt-3 max-w-[340px] text-sm text-gray-500 font-light">
                  Select an equity and a horizon, then run inference to see the forecast.
                </p>
              </motion.div>
            )}

            {!loading && forecastResults && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="flex flex-col"
              >
                {simulated && (
                  <div className="border-b border-gray-800 px-6 md:px-8 py-3 text-[10px] font-mono tracking-widest uppercase text-yellow-500/90">
                    Prediction API not connected — showing simulated output
                  </div>
                )}

                {/* Summary cells */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-gray-800 border-b border-gray-800">
                  {[
                    { label: 'Model', value: forecastResults.model_version },
                    { label: 'Avg confidence', value: `${forecastResults.average_confidence}%` },
                    { label: 'RSI (14D)', value: forecastResults.rsi_metric },
                  ].map(cell => (
                    <div key={cell.label} className="bg-[#0a0a0a] px-6 md:px-8 py-6">
                      <MonoLabel className="block mb-3">{cell.label}</MonoLabel>
                      <span className="text-xl font-normal tracking-tight">{cell.value}</span>
                    </div>
                  ))}
                </div>

                <div className="px-4 md:px-6 py-6 border-b border-gray-800">
                  <StockChart
                    ticker={forecastResults.ticker}
                    predictions={forecastResults.predictions.map(p => p.predicted_price)}
                    height={260}
                  />
                </div>

                {/* Forecast grid */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 text-left">
                        {['Date', 'Horizon', 'Predicted price', 'Trend', 'Confidence'].map(h => (
                          <th key={h} className="px-6 md:px-8 py-4 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {forecastResults.predictions.map((pred) => (
                        <tr key={pred.day} className="border-b border-gray-800/60 hover:bg-white/[0.02] transition-colors">
                          <td className="px-6 md:px-8 py-4 text-gray-200">{pred.date}</td>
                          <td className="px-6 md:px-8 py-4 font-mono text-gray-400">T+{pred.day}</td>
                          <td className="px-6 md:px-8 py-4 font-mono text-white">
                            ₹{pred.predicted_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-6 md:px-8 py-4">
                            <span className={`px-3 py-1 rounded-full border text-[10px] font-medium tracking-wider
                              ${pred.direction === 'BULLISH' ? 'border-green-500/40 text-green-500' : 'border-red-400/40 text-red-400'}`}>
                              {pred.direction}
                            </span>
                          </td>
                          <td className="px-6 md:px-8 py-4 font-mono text-gray-400">{pred.confidence}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="px-6 md:px-8 py-5 flex items-center gap-2 text-[10px] font-mono tracking-widest uppercase text-gray-500">
                  <Calendar size={13} /> Forecasts are model estimates, not investment advice.
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>

      <div className="px-6 md:px-16 py-8 text-[10px] font-mono tracking-widest text-gray-500 uppercase">
        Quantifying the impact of global financial news
      </div>
    </div>
  );
};

export default Predictor;
