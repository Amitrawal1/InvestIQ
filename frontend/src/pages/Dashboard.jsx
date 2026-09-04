import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import StockChart from '../components/StockChart';
import { DollarSign, Percent, Eye, Play, Plus, Trash2, ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';

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

  const handleSearch = (term) => {
    setSearchTerm(term);
  };

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

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Navbar onSearch={handleSearch} />

        {/* Dashboard Title & Overview */}
        <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '28px', color: '#fff', marginBottom: '4px' }}>Trading Terminal</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
              Real-time analytics and predictive indices powered by Python scikit-learn models.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <span style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(255,255,255,0.03)',
              padding: '8px 16px',
              borderRadius: '20px',
              border: '1px solid var(--border-color)',
              fontSize: '12px',
              color: 'var(--text-secondary)'
            }}>
              <Activity size={14} className="pulse-glow" style={{ color: 'var(--primary)' }} /> Live Data
            </span>
          </div>
        </div>

        {/* Metrics Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '20px',
          marginTop: '24px'
        }}>
          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Portfolio Value</span>
              <DollarSign size={18} color="var(--primary)" />
            </div>
            <h3 style={{ fontSize: '24px', color: '#fff' }}>₹12,45,210.00</h3>
            <span className="trend-up" style={{ fontSize: '12px', display: 'flex', alignItems: 'center', marginTop: '4px' }}>
              <ArrowUpRight size={14} /> +₹18,240 (1.48%)
            </span>
          </div>

          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Today's Return</span>
              <Percent size={18} color="var(--accent-purple)" />
            </div>
            <h3 style={{ fontSize: '24px', color: '#fff' }}>+₹8,452.20</h3>
            <span className="trend-up" style={{ fontSize: '12px', display: 'flex', alignItems: 'center', marginTop: '4px' }}>
              <ArrowUpRight size={14} /> +0.68%
            </span>
          </div>

          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Watchlist Size</span>
              <Eye size={18} color="var(--secondary)" />
            </div>
            <h3 style={{ fontSize: '24px', color: '#fff' }}>{watchlist.length} Assets</h3>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
              Monitoring custom listings
            </span>
          </div>

          <div className="glass-panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Model Inference Status</span>
              <Play size={18} color="var(--accent-neon)" />
            </div>
            <h3 style={{ fontSize: '24px', color: 'var(--accent-neon)' }}>ACTIVE</h3>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
              FastAPI prediction listener OK
            </span>
          </div>
        </div>

        {/* Dashboard Workstation Grid */}
        <div className="dashboard-grid">
          {/* Main Chart Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--primary)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  ANALYTICS CHART
                </span>
                <h2 style={{ fontSize: '22px', color: '#fff', marginTop: '4px' }}>
                  {selectedStockData.ticker} - {selectedStockData.name}
                </h2>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '22px', fontWeight: 700, color: '#fff' }}>
                  ₹{selectedStockData.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center', justifyContent: 'flex-end', marginTop: '2px' }}>
                  {selectedStockData.change >= 0 ? (
                    <span className="trend-up" style={{ fontSize: '13px', display: 'flex', alignItems: 'center' }}>
                      <ArrowUpRight size={14} /> +{selectedStockData.change}%
                    </span>
                  ) : (
                    <span className="trend-down" style={{ fontSize: '13px', display: 'flex', alignItems: 'center' }}>
                      <ArrowDownRight size={14} /> {selectedStockData.change}%
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Custom Interactive Stock Chart */}
            <StockChart ticker={selectedTicker} />

            <div style={{
              display: 'flex',
              gap: '12px',
              background: 'rgba(0, 242, 254, 0.05)',
              border: '1px solid rgba(0, 242, 254, 0.15)',
              padding: '12px 16px',
              borderRadius: '12px',
              fontSize: '13px',
              color: 'var(--text-secondary)'
            }}>
              <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>AI Insight:</span>
              <span>
                {selectedTicker === 'RELIANCE' && "Reliance has established a solid base support at 2430. Model suggests bullish continuation over the next 5 days."}
                {selectedTicker === 'TCS' && "TCS displays strong resistance around 3900. Short-term console pattern expected followed by breakdown breakout."}
                {selectedTicker === 'INFY' && "Infosys is exhibiting slight downward momentum due to global tech adjustments. Model forecasts a short consolidation near 1400."}
                {selectedTicker === 'HDFCBANK' && "HDFC Bank exhibits a stable accumulation phase. Safe risk-adjusted entry profile."}
                {!['RELIANCE', 'TCS', 'INFY', 'HDFCBANK'].includes(selectedTicker) && "Inference pipeline predicts stable trend progression for this asset."}
              </span>
            </div>
          </div>

          {/* Sidebar Panel for watchlist/stocks */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Watchlist Panel */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '16px', color: '#fff', marginBottom: '16px' }}>My Watchlist</h3>
              {watchlist.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: '13px' }}>
                  No stocks added yet. Use search below.
                </div>
              ) : (
                watchlist.map(stock => (
                  <div 
                    key={stock.ticker}
                    onClick={() => setSelectedTicker(stock.ticker)}
                    className="stock-card"
                    style={{
                      borderColor: selectedTicker === stock.ticker ? 'var(--primary)' : 'var(--border-color)',
                      boxShadow: selectedTicker === stock.ticker ? '0 0 10px rgba(0, 242, 254, 0.1)' : 'none'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '14px' }}>{stock.ticker}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>
                        {stock.name}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '13px', fontWeight: 600 }}>₹{stock.price.toFixed(2)}</div>
                        <div style={{ fontSize: '11px' }} className={stock.change >= 0 ? 'trend-up' : 'trend-down'}>
                          {stock.change >= 0 ? '+' : ''}{stock.change}%
                        </div>
                      </div>
                      <button 
                        onClick={(e) => removeFromWatchlist(stock.ticker, e)}
                        style={{
                          background: 'rgba(255, 23, 68, 0.1)',
                          border: 'none',
                          borderRadius: '6px',
                          color: 'var(--danger)',
                          padding: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Quick Listing Search Results */}
            <div className="glass-panel" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '16px', color: '#fff', marginBottom: '12px' }}>Market Securities</h3>
              <div style={{
                maxHeight: '220px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                paddingRight: '4px'
              }}>
                {filteredStocks.map(stock => (
                  <div 
                    key={stock.ticker}
                    onClick={() => setSelectedTicker(stock.ticker)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 12px',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'var(--transition-smooth)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
                  >
                    <div>
                      <span style={{ fontWeight: 600, fontSize: '13px' }}>{stock.ticker}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                        {stock.ticker}
                      </span>
                    </div>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        addToWatchlist(stock);
                      }}
                      style={{
                        background: 'rgba(0, 242, 254, 0.1)',
                        border: 'none',
                        color: 'var(--primary)',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '11px',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      <Plus size={12} /> Watch
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
