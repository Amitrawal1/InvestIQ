import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Brain, Lock, Mail, User, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [validationError, setValidationError] = useState('');

  const { login, register, error } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError('');

    if (!email || !password || (isRegister && !username)) {
      setValidationError('All fields are required');
      return;
    }

    let success = false;
    if (isRegister) {
      success = await register(username, email, password);
    } else {
      success = await login(email, password);
    }

    if (success) {
      navigate('/dashboard');
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      width: '100vw',
      background: 'radial-gradient(circle at center, #111827 0%, #030712 100%)',
      padding: '20px'
    }}>
      {/* Background Glows */}
      <div style={{
        position: 'absolute',
        width: '300px',
        height: '300px',
        background: 'rgba(0, 242, 254, 0.15)',
        filter: 'blur(100px)',
        top: '20%',
        left: '30%',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        width: '350px',
        height: '350px',
        background: 'rgba(138, 43, 226, 0.12)',
        filter: 'blur(120px)',
        bottom: '20%',
        right: '30%',
        pointerEvents: 'none'
      }} />

      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '440px',
        padding: '40px',
        textAlign: 'center',
        background: 'rgba(22, 33, 58, 0.45)',
        border: '1px solid rgba(255, 255, 255, 0.08)'
      }}>
        {/* Brand Icon */}
        <div style={{
          display: 'inline-flex',
          background: 'linear-gradient(135deg, var(--secondary) 0%, var(--primary) 100%)',
          width: '56px',
          height: '56px',
          borderRadius: '16px',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '24px',
          boxShadow: '0 0 25px rgba(0, 242, 254, 0.35)'
        }}>
          <Brain size={30} color="#000" />
        </div>

        <h1 style={{ fontSize: '28px', fontFamily: 'var(--font-display)', fontWeight: 800, marginBottom: '8px' }}>
          {isRegister ? 'Create Account' : 'Welcome Back'}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '32px' }}>
          {isRegister ? 'Join the AI-powered quantitative trading platform' : 'Access your predictive terminal and Zerodha dashboard'}
        </p>

        {/* Error Messages */}
        {(error || validationError) && (
          <div style={{
            background: 'rgba(255, 23, 68, 0.1)',
            border: '1px solid var(--danger)',
            color: 'var(--danger)',
            padding: '12px',
            borderRadius: '8px',
            fontSize: '13px',
            textAlign: 'left',
            marginBottom: '20px',
            fontWeight: 500
          }}>
            {error || validationError}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {isRegister && (
            <div style={{ position: 'relative' }}>
              <input 
                type="text" 
                placeholder="Username" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                style={{ paddingLeft: '44px' }}
              />
              <User size={18} style={{
                position: 'absolute',
                left: '16px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)'
              }} />
            </div>
          )}

          <div style={{ position: 'relative' }}>
            <input 
              type="email" 
              placeholder="Email Address" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '44px' }}
            />
            <Mail size={18} style={{
              position: 'absolute',
              left: '16px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)'
            }} />
          </div>

          <div style={{ position: 'relative' }}>
            <input 
              type="password" 
              placeholder="Secure Password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '44px' }}
            />
            <Lock size={18} style={{
              position: 'absolute',
              left: '16px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)'
            }} />
          </div>

          <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '8px' }}>
            {isRegister ? 'Sign Up' : 'Sign In'} <ArrowRight size={18} />
          </button>
        </form>

        <div style={{ marginTop: '24px', fontSize: '13px' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            {isRegister ? 'Already have an account? ' : 'New to BullStack? '}
          </span>
          <button 
            onClick={() => {
              setIsRegister(!isRegister);
              setValidationError('');
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--primary)',
              cursor: 'pointer',
              fontWeight: 600,
              textDecoration: 'underline'
            }}
          >
            {isRegister ? 'Sign In' : 'Create an account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
