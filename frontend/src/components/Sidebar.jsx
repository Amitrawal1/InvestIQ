import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Brain, Cpu, Database, Link2, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
  const { logout } = useAuth();

  return (
    <aside style={{
      width: '260px',
      background: 'var(--bg-sidebar)',
      backdropFilter: 'blur(20px)',
      borderRight: '1px solid var(--border-color)',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      top: 0,
      bottom: 0,
      left: 0,
      zIndex: 11
    }}>
      {/* Brand Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '40px' }}>
        <div style={{
          background: 'linear-gradient(135deg, var(--secondary) 0%, var(--primary) 100%)',
          width: '40px',
          height: '40px',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(0, 242, 254, 0.3)'
        }}>
          <Brain size={22} color="#000" />
        </div>
        <div>
          <h2 style={{ fontSize: '20px', fontFamily: 'var(--font-display)', fontWeight: 800, color: '#fff', lineHeight: 1 }}>
            BULLSTACK
          </h2>
          <span style={{ fontSize: '10px', color: 'var(--primary)', letterSpacing: '0.15em', fontWeight: 700 }}>
            AI PREDICTOR
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
        <NavLink 
          to="/dashboard"
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 16px',
            borderRadius: '10px',
            color: isActive ? '#000' : 'var(--text-secondary)',
            background: isActive ? 'linear-gradient(135deg, var(--secondary) 0%, var(--primary) 100%)' : 'transparent',
            textDecoration: 'none',
            fontSize: '14px',
            fontWeight: 600,
            transition: 'var(--transition-smooth)'
          })}
        >
          <LayoutDashboard size={20} />
          Dashboard
        </NavLink>

        <NavLink 
          to="/predictor"
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 16px',
            borderRadius: '10px',
            color: isActive ? '#000' : 'var(--text-secondary)',
            background: isActive ? 'linear-gradient(135deg, var(--secondary) 0%, var(--primary) 100%)' : 'transparent',
            textDecoration: 'none',
            fontSize: '14px',
            fontWeight: 600,
            transition: 'var(--transition-smooth)'
          })}
        >
          <Brain size={20} />
          AI Forecasts
        </NavLink>
      </nav>

      {/* Integration Status (Telemetry) */}
      <div className="glass-panel" style={{ padding: '16px', borderRadius: '12px', marginBottom: '24px' }}>
        <h4 style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: '12px', textTransform: 'uppercase' }}>
          System Telemetry
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Link2 size={14} /> Zerodha API
            </span>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>Active</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Database size={14} /> MongoDB
            </span>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>Connected</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
              <Cpu size={14} /> AI Engine
            </span>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>Online</span>
          </div>
        </div>
      </div>

      {/* Log out footer */}
      <button 
        onClick={logout}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          borderRadius: '10px',
          color: 'var(--danger)',
          background: 'rgba(255, 23, 68, 0.05)',
          border: '1px solid rgba(255, 23, 68, 0.1)',
          cursor: 'pointer',
          fontSize: '14px',
          fontWeight: 600,
          transition: 'var(--transition-smooth)'
        }}
      >
        <LogOut size={20} />
        Sign Out
      </button>
    </aside>
  );
};

export default Sidebar;
