import React, { useEffect, useRef, useState } from 'react';
import { getAuthConfig } from '../services/api';
import { useTheme } from '../context/ThemeContext';

// "Continue with Google" via Google Identity Services. The button itself is drawn by Google (an
// iframe, so only its theme/shape/width can be set). Renders nothing when the server has no
// GOOGLE_CLIENT_ID, so email sign-in keeps working on its own.

const GSI_SRC = 'https://accounts.google.com/gsi/client';

let configPromise = null;
const loadClientId = () => {
  if (!configPromise) {
    configPromise = getAuthConfig()
      .then((c) => c.google_client_id || null)
      .catch(() => { configPromise = null; return null; });
  }
  return configPromise;
};

let scriptPromise = null;
const loadScript = () => {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = GSI_SRC;
      el.async = true;
      el.onload = resolve;
      el.onerror = () => { scriptPromise = null; reject(new Error('Google script failed to load')); };
      document.head.appendChild(el);
    });
  }
  return scriptPromise;
};

export default function GoogleSignIn({ onCredential, text = 'continue_with', disabled = false }) {
  const { theme } = useTheme();
  const slot = useRef(null);
  const handler = useRef(onCredential);
  const [clientId, setClientId] = useState(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  handler.current = onCredential;

  useEffect(() => {
    let alive = true;
    loadClientId().then((id) => {
      if (!alive || !id) return;
      setClientId(id);
      loadScript().then(() => alive && setReady(true)).catch(() => alive && setFailed(true));
    });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!ready || !clientId || !slot.current) return;
    const gsi = window.google.accounts.id;
    gsi.initialize({
      client_id: clientId,
      callback: (res) => res?.credential && handler.current(res.credential),
      ux_mode: 'popup',
      context: text === 'signup_with' ? 'signup' : 'signin',
    });
    slot.current.innerHTML = '';
    gsi.renderButton(slot.current, {
      type: 'standard',
      theme: theme === 'light' ? 'outline' : 'filled_black',
      size: 'large',
      shape: 'pill',
      text,
      logo_alignment: 'center',
      width: Math.min(400, Math.max(200, slot.current.offsetWidth || 320)),
    });
  }, [ready, clientId, theme, text]);

  if (!clientId) return null;

  return (
    <div className="space-y-8">
      <div
        ref={slot}
        className={`w-full min-h-[44px] flex justify-center ${disabled ? 'pointer-events-none opacity-50' : ''}`}
        aria-busy={!ready}
      />
      {failed && (
        <p className="text-[11px] font-mono tracking-wider uppercase text-gray-500 text-center">
          Google sign-in couldn't load. Use email below.
        </p>
      )}
      <div className="flex items-center gap-4 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-600">
        <span className="h-px flex-1 bg-gray-800" />
        or with email
        <span className="h-px flex-1 bg-gray-800" />
      </div>
    </div>
  );
}
