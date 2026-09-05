import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Search, Bell, TrendingUp, LogOut } from 'lucide-react';

const Navbar = ({ onSearch }) => {
  const { user, logout } = useAuth();

  const handleSearchChange = (e) => {
    if (onSearch) {
      onSearch(e.target.value);
    }
  };

  return (
    <nav className="w-full sticky top-0 z-10 flex items-center justify-between px-6 py-4 bg-[#050011]">
      {/* Left - Market Info */}
      <div className="flex items-center gap-5 text-[13px]">
        <div className=" items-center gap-1.5">
          <span className="text-[var(--text-muted)]">NIFTY 50:</span>
          <span className="flex items-center gap-0.5 text-[var(--success)]">
            22,957.10 (+0.82%)
            <TrendingUp size={14} />
          </span>
        </div>

        <div className=" items-center gap-1.5">
          <span className="text-[var(--text-muted)]">SENSEX:</span>
          <span className="flex items-center gap-0.5 text-[var(--success)]">
            75,410.35 (+0.78%)
            <TrendingUp size={14} />
          </span>
        </div>
      </div>


      {/* Center - Search */}
      <div className="relative w-[420px]">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />

        <input
          type="text"
          placeholder="Search NSE stocks (e.g., RELIANCE, TCS)..."
          onChange={handleSearchChange}
          className="w-full pl-10 pr-4 py-2.5 rounded-[20px] bg-[#0d1423] text-white text-sm outline-none border-none placeholder:text-[var(--text-muted)]"
        />
      </div>


      {/* Right - User */}
      <div className="flex items-center gap-4">

        {/* Notification */}
        <button className="relative flex items-center justify-center bg-transparent border-none text-[var(--text-secondary)] cursor-pointer">
          <Bell size={20} />

          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[var(--primary)] pulse-glow" />
        </button>


        {/* User */}
        <div className="flex items-center gap-2.5">

          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--accent-purple)] to-[var(--primary)] flex items-center justify-center text-sm font-bold text-white">
            {user?.username ? user.username[0].toUpperCase() : 'U'}
          </div>

          <div className="text-left">
            <div className="text-sm font-semibold text-white">
              {user?.username || 'Demo User'}
            </div>

            <div className="text-[11px] text-[var(--text-muted)]">
              Trader Profile
            </div>
          </div>

          {/* Logout */}
          <button
            onClick={logout}
            title="Log out"
            className="ml-2 flex items-center bg-transparent border-none text-[var(--danger)] cursor-pointer"
          >
            <LogOut size={18} />
          </button>

        </div>

      </div>

    </nav>
  );
};

export default Navbar;