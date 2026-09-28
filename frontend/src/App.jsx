import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Predictor from './pages/Predictor';
import Landing from './pages/Landing';
import Intro from './pages/Intro';
import Home from './pages/Home';
import Sector from './pages/Sector';
import News from './pages/News';
import Company from './pages/Company';
import Settings from './pages/Settings';
import Portfolio from './pages/Portfolio';


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
        <Routes>
          {/* Intro is the design reference and always renders dark: .theme-dark restores the dark tokens for its subtree */}
          <Route path="" element={<div className="theme-dark"><Intro /></div>} />
          <Route path="login" element={<Login />} />
          <Route path="home" element={<Home />} />
          <Route path="sectors/:slug" element={<Sector />} />
          <Route path="news" element={<News />} />
          <Route path="company/:symbol" element={<Company />} />
          <Route path="dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="predictor" element={<PrivateRoute><Predictor /></PrivateRoute>} />
          <Route path="portfolio" element={<PrivateRoute><Portfolio /></PrivateRoute>} />
          <Route path="settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
          <Route path="landing/" element={<Landing />} />
          {/* Fallback paths redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
