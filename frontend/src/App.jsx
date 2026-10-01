import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { MotionConfig } from 'motion/react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Login from './pages/Login';
import Predictor from './pages/Predictor';
import Intro from './pages/Intro';
import Home from './pages/Home';
import Sector from './pages/Sector';
import News from './pages/News';
import Company from './pages/Company';
import Settings from './pages/Settings';
import Portfolio from './pages/Portfolio';
import About from './pages/About';
import Help from './pages/Help';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import Disclaimer from './pages/Disclaimer';
import NotFound from './pages/NotFound';
import TrackRecord from './pages/TrackRecord';


// New page -> start at the top (links like /home#sectors scroll to their section instead)
const ScrollToTop = () => {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname, hash]);
  return null;
};

// App pages honour the OS "reduce motion" setting (Intro, the design reference, is left as is)
const AppMotion = () => (
  <MotionConfig reducedMotion="user">
    <Outlet />
  </MotionConfig>
);

// Protect private views from unauthenticated requests
const PrivateRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-page text-white font-sans" role="status" aria-label="Loading">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-gray-800 border-t-accent" />
      </div>
    );
  }
  // Remember where the user was headed so Login can send them back
  return user ? children : <Navigate to="/login" replace state={{ from: location }} />;
};

const App = () => {
  return (
    <ThemeProvider>
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <Routes>
          {/* Intro is the design reference and always renders dark: .theme-dark restores the dark tokens for its subtree */}
          <Route path="" element={<div className="theme-dark"><Intro /></div>} />
          <Route element={<AppMotion />}>
            <Route path="login" element={<Login />} />
            <Route path="home" element={<Home />} />
            <Route path="sectors/:slug" element={<Sector />} />
            <Route path="news" element={<News />} />
            <Route path="company/:symbol" element={<Company />} />
            {/* The old demo dashboard is gone: the real one is Portfolio */}
            <Route path="dashboard" element={<Navigate to="/portfolio" replace />} />
            <Route path="predictor" element={<PrivateRoute><Predictor /></PrivateRoute>} />
            <Route path="portfolio" element={<PrivateRoute><Portfolio /></PrivateRoute>} />
            <Route path="settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
            {/* Company, support and legal pages (public) */}
            <Route path="track-record" element={<TrackRecord />} />
            <Route path="about" element={<About />} />
            <Route path="help" element={<Help />} />
            <Route path="contact" element={<Navigate to="/help#contact" replace />} />
            <Route path="privacy" element={<Privacy />} />
            <Route path="terms" element={<Terms />} />
            <Route path="disclaimer" element={<Disclaimer />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
