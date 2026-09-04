import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Search, Bell, TrendingUp, ShieldAlert, LogOut } from 'lucide-react';

const Navbar = ({ onSearch }) => {
  const { user, logout } = useAuth();

  const handleSearchChange = (e) => {
    if (onSearch) {
      onSearch(e.target.value);
    }
  };

  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 24px',
      background: 'rgba(13, 20, 35, 0.4)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid var(--border-color)',
      position: 'sticky',
      top: 0,
      zIndex: 10,
      borderRadius: '0 0 16px 16px'
    }}>
      {/* Search Bar */}
      <div style={{ position: 'relative', width: '320px' }}>
        <input 
          type="text" 
          placeholder="Search NSE stocks (e.g., RELIANCE, TCS)..." 
          onChange={handleSearchChange}
          className="input-field"
          style={{ paddingLeft: '40px', borderRadius: '20px' }}
        />
        <Search size={18} style={{
          position: 'absolute',
          left: '14px',
          top: '50%',
          transform: 'translateY(-50%)',
          color: 'var(--text-muted)'
        }} />
      </div>

      {/* Center Market Info */}
      <div style={{ display: 'flex', gap: '20px', fontSize: '13px', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--text-muted)' }}>NIFTY 50:</span>
          <span className="trend-up" style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
            22,957.10 (+0.82%) <TrendingUp size={14} />
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--text-muted)' }}>SENSEX:</span>
          <span className="trend-up" style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
            75,410.35 (+0.78%) <TrendingUp size={14} />
          </span>
        </div>
        <div style={{
          background: 'rgba(0, 230, 118, 0.1)',
          border: '1px solid var(--success)',
          padding: '2px 8px',
          borderRadius: '20px',
          color: 'var(--success)',
          fontSize: '11px',
          fontWeight: 600,
          letterSpacing: '0.05em'
        }}>
          MARKET OPEN
        </div>
      </div>

      {/* User Information */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          position: 'relative'
        }}>
          <Bell size={20} />
          <span style={{
            position: 'absolute',
            top: '-2px',
            right: '-2px',
            background: 'var(--primary)',
            width: '8px',
            height: '8px',
            borderRadius: '50%'
          }} className="pulse-glow" />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-purple) 0%, var(--primary) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '14px',
            fontWeight: 700,
            color: '#fff'
          }}>
            {user?.username ? user.username[0].toUpperCase() : 'U'}
          </div>
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '14px', fontWeight: 600 }}>{user?.username || 'Demo User'}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Trader Profile</div>
          </div>
          
          <button 
            onClick={logout}
            title="Log out"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--danger)',
              cursor: 'pointer',
              marginLeft: '8px',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
