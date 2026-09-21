import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowUpRight, Plus, X } from 'lucide-react';
import Navbar from '../components/Navbar';
import StockChart from '../components/StockChart';
import { PageHeading, MonoLabel, LiveDot, Change } from '../components/ui';

const insights = {
  RELIANCE: "Reliance has established a solid base support at 2430. Model suggests bullish continuation over the next 5 days.",
  TCS: "TCS displays strong resistance around 3900. A short-term consolidation is expected before the next breakout.",
  INFY: "Infosys is exhibiting slight downward momentum due to global tech adjustments. Model forecasts a short consolidation near 1400.",
  HDFCBANK: "HDFC Bank exhibits a stable accumulation phase. Safe risk-adjusted entry profile.",
};

const Dashboard = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTicker, setSelectedTicker] = useState('RELIANCE');

  // High-fidelity Mock Stocks
  const [watchlist, setWatchlist] = useState([
    { ticker: 'RELIANCE', name: 'Reliance Industries Ltd.', price: 2460.50, change: 1.45 },
    { ticker: 'TCS', name: 'Tata Consultancy Services', price: 3855.20, change: 0.85 },
    { ticker: 'INFY', name: 'Infosys Limited', price: 1412.10, change: -1.20 },
    { ticker: 'HDFCBANK', name: 'HDFC Bank Limited', price: 1548.80, change: 0.35 }
  ]);

  const [availableStocks] = useState([
    { ticker: 'RELIANCE', name: 'Reliance Industries Ltd.', price: 2460.50, change: 1.45 },
    { ticker: 'TCS', name: 'Tata Consultancy Services', price: 3855.20, change: 0.85 },
    { ticker: 'INFY', name: 'Infosys Limited', price: 1412.10, change: -1.20 },
    { ticker: 'HDFCBANK', name: 'HDFC Bank Limited', price: 1548.80, change: 0.35 },
    { ticker: 'WIPRO', name: 'Wipro Limited', price: 462.40, change: -0.75 },
    { ticker: 'ICICIBANK', name: 'ICICI Bank Ltd.', price: 1125.15, change: 2.10 },
    { ticker: 'SBIN', name: 'State Bank of India', price: 830.60, change: 1.80 }
  ]);

  const addToWatchlist = (stock) => {
    if (!watchlist.find(item => item.ticker === stock.ticker)) {
      setWatchlist([...watchlist, stock]);
    }
  };

  const removeFromWatchlist = (ticker, e) => {
    e.stopPropagation(); // Avoid selecting stock when clicking delete
    setWatchlist(watchlist.filter(item => item.ticker !== ticker));
  };

  // Filter available stocks based on search query
  const filteredStocks = availableStocks.filter(stock =>
    stock.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
    stock.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedStockData = availableStocks.find(s => s.ticker === selectedTicker) || availableStocks[0];

  const metrics = [
    { label: 'Portfolio Value', value: '₹12,45,210.00', sub: <><Change value={1.48} /> <span className="text-gray-500">+₹18,240</span></> },
    { label: "Today's Return", value: '+₹8,452.20', sub: <Change value={0.68} /> },
    { label: 'Watchlist Size', value: `${watchlist.length} Assets`, sub: <span className="text-gray-500">Monitoring custom listings</span> },
    { label: 'Model Status', value: 'ACTIVE', sub: <span className="text-gray-500">Prediction service ready</span>, live: true },
  ];

  return (
    <div className="min-h-screen w-full bg-[#050011] text-white font-sans">
      <Navbar onSearch={setSearchTerm} />

      <div className="px-6 md:px-16 pt-12 md:pt-16 pb-12">
        <PageHeading index="02" label="Terminal" title="TRADING TERMINAL">
          <div className="flex flex-col lg:items-end gap-4">
            <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed lg:text-right">
              Real-time analytics and<br className="hidden lg:block" /> predictive signals on NSE equities.
            </p>
            <span className="flex items-center gap-2 w-fit px-4 py-2 rounded-full border border-gray-600 bg-white/5 text-[11px] font-medium uppercase tracking-wider text-gray-300">
              <LiveDot /> Live data
            </span>
          </div>
        </PageHeading>
      </div>

      {/* METRICS - hairline grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-px bg-gray-800 border-y border-gray-800">
        {metrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 + i * 0.08 }}
            className="bg-[#0a0a0a] px-6 md:px-8 py-8"
          >
            <div className="flex justify-between items-center mb-6">
              <MonoLabel>{m.label}</MonoLabel>
              <span className="text-[10px] font-mono text-gray-600">0{i + 1}</span>
            </div>
            <div className="text-[1.8rem] md:text-[2.2rem] font-normal tracking-tight leading-none flex items-center gap-3">
              {m.live && <LiveDot className="w-2 h-2" />}
              {m.value}
            </div>
            <div className="mt-3 text-xs">{m.sub}</div>
          </motion.div>
        ))}
      </section>

      {/* WORKSTATION - two-column panel */}
      <section className="w-full flex flex-col lg:flex-row bg-[#0a0a0a] border-b border-gray-800">
        {/* Chart column */}
        <div className="w-full lg:w-[65%] border-b lg:border-b-0 lg:border-r border-gray-800 flex flex-col">
          <div className="border-b border-gray-800 px-6 md:px-8 py-5 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
            <span>Analytics chart</span>
            <span>{selectedStockData.ticker}</span>
          </div>

          <div className="px-6 md:px-8 pt-8 flex flex-col sm:flex-row justify-between sm:items-end gap-4">
            <div>
              <h2 className="text-[2rem] md:text-[2.6rem] font-medium tracking-tight leading-none">
                {selectedStockData.ticker}
              </h2>
              <p className="mt-2 text-sm text-gray-400">{selectedStockData.name}</p>
            </div>
            <div className="sm:text-right">
              <div className="text-[1.8rem] font-normal tracking-tight leading-none">
                ₹{selectedStockData.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <Change value={selectedStockData.change} className="text-sm mt-2 inline-block" />
            </div>
          </div>

          <div className="px-4 md:px-6 py-6">
            <StockChart ticker={selectedTicker} height={440} />
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={selectedTicker}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
              className="mt-auto border-t border-gray-800 px-6 md:px-8 py-6 flex flex-col sm:flex-row gap-3 sm:gap-6"
            >
              <span className="flex items-center gap-2 shrink-0 text-[10px] font-mono tracking-widest uppercase text-white">
                <span className="w-1.5 h-1.5 rounded-full bg-[#d942ff]" /> AI Insight
              </span>
              <p className="text-sm text-gray-400 leading-relaxed font-light">
                {insights[selectedTicker] || "Inference pipeline predicts stable trend progression for this asset."}
              </p>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Lists column */}
        <div className="w-full lg:w-[35%] flex flex-col">
          {/* Watchlist */}
          <div className="border-b border-gray-800 px-6 md:px-8 py-5 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
            <span>My watchlist</span>
            <span>{String(watchlist.length).padStart(2, '0')}</span>
          </div>

          {watchlist.length === 0 ? (
            <div className="px-8 py-12 text-center text-[10px] font-mono tracking-widest uppercase text-gray-500">
              No stocks added yet. Search below.
            </div>
          ) : (
            watchlist.map(stock => {
              const isActive = selectedTicker === stock.ticker;
              return (
                <div
                  key={stock.ticker}
                  onClick={() => setSelectedTicker(stock.ticker)}
                  className={`group border-b border-gray-800/80 px-6 md:px-8 py-5 flex justify-between items-center cursor-pointer transition-colors duration-300 ${isActive ? 'text-white' : 'text-[#555] hover:text-[#aaa]'}`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xl font-medium tracking-tight">{stock.ticker}</h3>
                      {isActive && <ArrowUpRight size={16} strokeWidth={1} className="text-gray-400" />}
                    </div>
                    <p className="text-[11px] truncate max-w-[180px] text-gray-500">{stock.name}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm font-mono">₹{stock.price.toFixed(2)}</div>
                      <Change value={stock.change} className="text-[11px]" />
                    </div>
                    <button
                      onClick={(e) => removeFromWatchlist(stock.ticker, e)}
                      title="Remove from watchlist"
                      className="w-7 h-7 flex items-center justify-center rounded-full border border-gray-700 text-gray-500 hover:border-red-400 hover:text-red-400 transition-colors cursor-pointer"
                    >
                      <X size={12} />
                    </button>
                  </div>
                </div>
              );
            })
          )}

          {/* Market securities */}
          <div className="border-b border-gray-800 px-6 md:px-8 py-5 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
            <span>Market securities</span>
            <span>{searchTerm ? `"${searchTerm}"` : 'All'}</span>
          </div>

          <div className="max-h-[300px] overflow-y-auto">
            {filteredStocks.length === 0 && (
              <div className="px-8 py-10 text-center text-[10px] font-mono tracking-widest uppercase text-gray-500">
                No matches
              </div>
            )}
            {filteredStocks.map(stock => {
              const watched = watchlist.some(w => w.ticker === stock.ticker);
              return (
                <div
                  key={stock.ticker}
                  onClick={() => setSelectedTicker(stock.ticker)}
                  className="border-b border-gray-800/60 px-6 md:px-8 py-3.5 flex justify-between items-center cursor-pointer text-gray-400 hover:text-white hover:bg-white/[0.02] transition-colors"
                >
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-gray-200">{stock.ticker}</span>
                    <span className="ml-3 text-[11px] text-gray-500 truncate">{stock.name}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      addToWatchlist(stock);
                    }}
                    disabled={watched}
                    className="shrink-0 flex items-center gap-1 px-3 py-1 rounded-full border border-gray-600 text-[10px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
                  >
                    {watched ? 'Watching' : <><Plus size={11} /> Watch</>}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <div className="px-6 md:px-16 py-8 text-[10px] font-mono tracking-widest text-gray-500 uppercase">
        Quantifying the impact of global financial news
      </div>
    </div>
  );
};

export default Dashboard;
