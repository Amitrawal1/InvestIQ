import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import * as authApi from '../services/api';
import { apiError } from '../services/api';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

const TOKEN_KEY = 'token';
// Profile edits used to be kept on this device before the account API existed
const LEGACY_PROFILE_KEY = 'investiq-profile';

const store = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
  },
};

// Expiry (ms) from the JWT payload; null when it can't be read
const tokenExpiry = (token) => {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const { exp } = JSON.parse(window.atob(part));
    return Number.isFinite(exp) ? exp * 1000 : null;
  } catch {
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // restoring the session on first load
  const [error, setError] = useState(null); // last login/register/session error
  const [sessionExpired, setSessionExpired] = useState(false);
  const expiryTimer = useRef(null);

  const clearSession = useCallback((expired = false) => {
    store.clear();
    clearTimeout(expiryTimer.current);
    setUser(null);
    setSessionExpired(expired);
    if (expired) setError('Your session has expired. Sign in again.');
  }, []);

  // Sign out on the dot when the JWT expires, rather than on the next failing request
  const scheduleExpiry = useCallback((token) => {
    clearTimeout(expiryTimer.current);
    const exp = tokenExpiry(token);
    if (!exp) return;
    const ms = exp - Date.now();
    if (ms <= 0) return;
    // setTimeout overflows past ~24.8 days; tokens last 7 days
    expiryTimer.current = setTimeout(() => clearSession(true), Math.min(ms, 2 ** 31 - 1));
  }, [clearSession]);

  const startSession = useCallback((token, userData) => {
    store.set(token);
    setUser(userData);
    setError(null);
    setSessionExpired(false);
    scheduleExpiry(token);
  }, [scheduleExpiry]);

  // Restore the session on mount
  useEffect(() => {
    try { localStorage.removeItem(LEGACY_PROFILE_KEY); } catch { /* ignore */ }

    const token = store.get();
    if (!token) {
      setLoading(false);
      return undefined;
    }
    const exp = tokenExpiry(token);
    if (exp && exp <= Date.now()) {
      clearSession(true);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    authApi
      .getMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        scheduleExpiry(token);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.response?.status === 401) clearSession(true);
        else setError(apiError(err, "Couldn't restore your session."));
        // Network/server errors keep the token so a reload can retry
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [clearSession, scheduleExpiry]);

  // Any authenticated request answered with 401 -> token is no longer valid
  useEffect(() => {
    const onUnauthorized = () => {
      if (store.get()) clearSession(true);
    };
    window.addEventListener('investiq:unauthorized', onUnauthorized);
    return () => {
      window.removeEventListener('investiq:unauthorized', onUnauthorized);
      clearTimeout(expiryTimer.current);
    };
  }, [clearSession]);

  const login = async (email, password) => {
    setError(null);
    try {
      const { token, user: userData } = await authApi.loginUser(email.trim(), password);
      startSession(token, userData);
      return true;
    } catch (err) {
      setError(apiError(err, 'Sign in failed. Try again.'));
      return false;
    }
  };

  const register = async (username, email, password) => {
    setError(null);
    try {
      const { token, user: userData } = await authApi.registerUser(username.trim(), email.trim(), password);
      startSession(token, userData);
      return true;
    } catch (err) {
      setError(apiError(err, "Couldn't create your account. Try again."));
      return false;
    }
  };

  // PATCH /auth/me. Resolves to { ok: true } or { ok: false, status, message }
  const updateProfile = async ({ username, email }) => {
    try {
      const next = await authApi.updateMe({ username: username.trim(), email: email.trim() });
      setUser(next);
      return { ok: true };
    } catch (err) {
      return { ok: false, status: err.response?.status, message: apiError(err, "Couldn't save your profile.") };
    }
  };

  const changePassword = async (currentPassword, newPassword) => {
    try {
      await authApi.changePassword(currentPassword, newPassword);
      return { ok: true };
    } catch (err) {
      return { ok: false, status: err.response?.status, message: apiError(err, "Couldn't change your password.") };
    }
  };

  // Deletes the account server-side, then signs out
  const deleteAccount = async (password) => {
    try {
      await authApi.deleteAccount(password);
      clearSession(false);
      return { ok: true };
    } catch (err) {
      return { ok: false, status: err.response?.status, message: apiError(err, "Couldn't delete your account.") };
    }
  };

  const logout = () => {
    clearSession(false);
    setError(null);
  };

  const clearError = () => setError(null);

  const value = {
    user,
    loading,
    error,
    sessionExpired,
    clearError,
    login,
    register,
    logout,
    updateProfile,
    changePassword,
    deleteAccount,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
