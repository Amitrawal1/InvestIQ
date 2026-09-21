import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Predictor from './pages/Predictor';
import Landing from './pages/Landing';
import Intro from './pages/Intro';
import Home from './pages/Home';
import Sector from './pages/Sector';


// Protect private views from unauthenticated requests
const PrivateRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050011] text-white font-sans">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-gray-800 border-t-[#d942ff]" />
      </div>
    );
  }
  return user ? children : <Navigate to="/login" replace />;
};

const App = () => {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="" element={<Intro />} />
          <Route path="login" element={<Login />} />
          <Route path="home" element={<Home />} />
          <Route path="sectors/:slug" element={<Sector />} />
          <Route path="dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="predictor" element={<PrivateRoute><Predictor /></PrivateRoute>} />
          <Route path="landing/" element={<Landing />} />
          {/* Fallback paths redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
};

export default App;
