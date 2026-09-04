import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Footer from '../components/Footer';
import { ArrowRight, Brain, Cpu, ShieldCheck, AreaChart, Zap } from 'lucide-react';

export default function Landing() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleEnterTerminal = () => {
    if (user) {
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen bg-[#F0F1F3] text-[#0f172a] font-sans antialiased overflow-x-hidden flex flex-col justify-between">
      {/* Top Navbar */}
      <header className="w-full max-w-6xl mx-auto px-6 py-6 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="bg-[#31A8FF] w-9 h-9 rounded-xl flex items-center justify-center shadow-md">
            <Brain size={20} color="#fff" />
          </div>
          <div>
            <span className="text-[20px] font-extrabold tracking-tight text-[#0F172A]">BULLSTACK</span>
            <span className="text-[9px] font-bold text-[#31A8FF] block tracking-widest mt-[-2px] uppercase">AI Engine</span>
          </div>
        </div>

        <button 
          onClick={handleEnterTerminal}
          className="px-5 py-2.5 bg-white hover:bg-slate-50 text-slate-800 font-semibold text-sm border border-slate-200/80 rounded-xl shadow-sm transition-all active:scale-95 flex items-center gap-2 cursor-pointer"
        >
          {user ? 'Go to Terminal' : 'Sign In'} <ArrowRight size={15} />
        </button>
      </header>

      {/* Hero Section */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-6 pt-12 pb-20 flex flex-col items-center text-center">
        {/* Badge */}
        <div className="px-4 py-1.5 bg-[#31A8FF]/10 text-[#31A8FF] border border-[#31A8FF]/20 rounded-full text-xs font-semibold tracking-wider uppercase mb-6 flex items-center gap-2">
          <Zap size={12} /> Live Zerodha & Scikit-Learn Ecosystem
        </div>

        {/* Headline */}
        <h1 className="text-[44px] sm:text-[60px] lg:text-[76px] font-extrabold tracking-tight text-[#0f172a] leading-[1.05] max-w-[900px] mb-8 font-sans">
          The future of <span className="text-[#31A8FF]">quantitative</span> stock forecasting.
        </h1>

        {/* Description */}
        <p className="text-slate-500 text-[18px] sm:text-[20px] font-normal leading-relaxed max-w-[640px] mb-10">
          Build complex watchlists, fetch low-latency NSE listing bars, and run automated machine learning model inferences directly inside a gorgeous, glassmorphic terminal.
        </p>

        {/* Main CTA */}
        <div className="flex flex-col sm:flex-row gap-4 mb-20 w-full justify-center">
          <button 
            onClick={handleEnterTerminal}
            className="px-8 py-4 bg-[#0F172A] hover:bg-[#1E293B] text-white font-semibold text-base rounded-2xl shadow-lg hover:shadow-xl transition-all active:scale-95 flex items-center justify-center gap-3 cursor-pointer"
          >
            Enter Trading Terminal <ArrowRight size={18} />
          </button>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full text-left mb-12">
          
          {/* Card 1 */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200/60 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:scale-[1.02] transition-all">
            <div className="w-12 h-12 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center mb-6">
              <Cpu className="text-indigo-600 w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-3">AI Neural Projections</h3>
            <p className="text-slate-500 leading-relaxed text-sm">
              Fit live pricing arrays with scikit-learn models. Generate recursive T+5 forecasts incorporating rolling moving averages and RSI markers.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200/60 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:scale-[1.02] transition-all">
            <div className="w-12 h-12 bg-[#31A8FF]/10 border border-[#31A8FF]/20 rounded-2xl flex items-center justify-center mb-6">
              <AreaChart className="text-[#31A8FF] w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-3">Zerodha SDK Hook</h3>
            <p className="text-slate-500 leading-relaxed text-sm">
              Connected server-side with Zerodha's Kite SDK. Complies with rate limits via MongoDB Bucket Pattern daily instrument cache schemas.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200/60 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:scale-[1.02] transition-all">
            <div className="w-12 h-12 bg-emerald-50 border border-emerald-100 rounded-2xl flex items-center justify-center mb-6">
              <ShieldCheck className="text-emerald-600 w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-3">Glassmorphic UI Workspace</h3>
            <p className="text-slate-500 leading-relaxed text-sm">
              Highly responsive visual design featuring glass panels, custom interactive charting layers, and tactile, high-speed watchlist filters.
            </p>
          </div>

        </div>
      </main>

      {/* Styled Footer Card & GlassText */}
      <Footer />
    </div>
  );
}
