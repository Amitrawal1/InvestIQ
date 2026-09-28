import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Logo from '../components/Logo';
import { fadeUp, stagger, SectionLabel, PrimaryButton, Panel } from '../components/ui';

const Field = ({ label, type = 'text', value, onChange, placeholder, autoComplete }) => (
  <label className="block">
    <span className="block text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-2">{label}</span>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={autoComplete}
      className="w-full bg-transparent border-b border-gray-700 pb-3 text-white text-[15px] outline-none placeholder:text-gray-600 focus:border-white transition-colors"
    />
  </label>
);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;

// Where to go after signing in: the page PrivateRoute bounced us from, else the portfolio
const destinationOf = (state) => {
  const from = state?.from;
  if (!from?.pathname || from.pathname === '/login') return '/portfolio';
  return `${from.pathname}${from.search || ''}${from.hash || ''}`;
};

const Login = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [validationError, setValidationError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const { login, register, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Typing clears a stale server error (e.g. "Invalid email or password")
  const edit = (setter) => (value) => {
    setter(value);
    if (validationError) setValidationError('');
    if (error) clearError();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError('');

    clearError();

    if (!email.trim() || !password || (isRegister && !username.trim())) {
      setValidationError('All fields are required');
      return;
    }
    if (!EMAIL_RE.test(email.trim())) {
      setValidationError('Enter a valid email address');
      return;
    }
    if (isRegister && username.trim().length < 2) {
      setValidationError('Username needs at least 2 characters');
      return;
    }
    if (isRegister && password.length < MIN_PASSWORD) {
      setValidationError(`Password needs at least ${MIN_PASSWORD} characters`);
      return;
    }

    setSubmitting(true);
    const success = isRegister
      ? await register(username, email, password)
      : await login(email, password);
    setSubmitting(false);

    if (success) {
      navigate(destinationOf(location.state), { replace: true });
    }
  };

  const message = validationError || error;

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans flex flex-col lg:flex-row">
      {/* LEFT - editorial panel */}
      <section className="relative lg:w-[55%] flex flex-col justify-between px-6 md:px-16 py-8 lg:py-10 border-b lg:border-b-0 lg:border-r border-gray-800 overflow-hidden">
        <div className="absolute inset-0 bg-[url('/bg.png')] bg-cover bg-center opacity-40 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-b from-page/40 via-page/60 to-page pointer-events-none" />

        <div className="relative z-10 flex items-center justify-between">
          <Logo className="text-xl" />
          <button
            onClick={() => navigate('/home')}
            className="flex items-center gap-2 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400 hover:text-white transition-colors cursor-pointer"
          >
            Explore first <ArrowUpRight size={14} strokeWidth={1} />
          </button>
        </div>

        <motion.div
          initial="initial"
          animate="animate"
          variants={stagger(0.2, 0.15)}
          className="relative z-10 py-20 lg:py-0"
        >
          <motion.div variants={fadeUp}>
            <SectionLabel index={isRegister ? '02' : '01'} className="mb-6">
              {isRegister ? 'New account' : 'Sign in'}
            </SectionLabel>
          </motion.div>
          <motion.h1
            variants={fadeUp}
            className="text-[3.2rem] md:text-[5rem] font-normal tracking-tight leading-[1]"
          >
            {isRegister ? <>START<br />INVESTING<br />SMARTER</> : <>WELCOME<br />BACK</>}
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-8 text-[14px] text-gray-300 max-w-[320px] leading-[1.6]">
            Decode financial news signals, track your watchlist and run AI forecasts on Indian equities.
          </motion.p>
        </motion.div>

        <div className="relative z-10 hidden lg:flex items-center gap-4 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400">
          <span>Stock</span><ArrowRight size={12} strokeWidth={1} />
          <span>News</span><ArrowRight size={12} strokeWidth={1} />
          <span>Trends</span>
        </div>
      </section>

      {/* RIGHT - form */}
      <section className="lg:w-[45%] flex items-center justify-center px-6 md:px-16 py-16">
        <Panel glow className="w-full max-w-[440px] p-8 md:p-10">
          <div className="flex justify-between items-start mb-10">
            <h2 className="text-xl md:text-2xl font-medium tracking-tight flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              {isRegister ? 'Create an account' : 'Sign in to InvestIQ'}
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            <AnimatePresence initial={false}>
              {isRegister && (
                <motion.div
                  key="username"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <Field label="Username" value={username} onChange={edit(setUsername)} placeholder="yourname" autoComplete="username" />
                </motion.div>
              )}
            </AnimatePresence>

            <Field label="Email" type="email" value={email} onChange={edit(setEmail)} placeholder="you@example.com" autoComplete="email" />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={edit(setPassword)}
              placeholder={isRegister ? 'At least 8 characters' : '••••••••'}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />

            {message && (
              <p role="alert" className="text-[11px] font-mono tracking-wider uppercase text-red-400">{message}</p>
            )}

            <PrimaryButton type="submit" icon={ArrowRight} disabled={submitting} className="w-full">
              {submitting ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}
            </PrimaryButton>
          </form>

          <div className="mt-10 pt-6 border-t border-gray-800 flex justify-between items-center text-[10px] font-mono tracking-widest uppercase text-gray-500">
            <span>{isRegister ? 'Already have an account?' : "Don't have an account?"}</span>
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister);
                setValidationError('');
                clearError();
              }}
              className="text-white hover:underline cursor-pointer"
            >
              {isRegister ? 'Sign in' : 'Create one'}
            </button>
          </div>
        </Panel>
      </section>
    </div>
  );
};

export default Login;
