import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "motion/react";
import { Check, LogOut, Monitor, Moon, Sun } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, Panel, MonoLabel, SectionLabel, PrimaryButton, fadeUp, stagger } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const validate = ({ username, email }) => {
  const errors = {};
  const name = username.trim();
  if (!name) errors.username = "Enter a display name";
  else if (name.length < 2) errors.username = "Use at least 2 characters";
  else if (name.length > 40) errors.username = "Use 40 characters or fewer";
  if (!email.trim()) errors.email = "Enter an email address";
  else if (!EMAIL_RE.test(email.trim())) errors.email = "Enter a valid email address";
  return errors;
};

const Section = ({ id, index, label, title, aside, children }) => (
  <motion.section
    id={id}
    initial="initial"
    whileInView="animate"
    viewport={{ once: true, margin: "-60px" }}
    variants={stagger(0, 0.08)}
    className="border-t border-gray-800 px-6 md:px-16 py-14 scroll-mt-[73px]"
  >
    <motion.div variants={fadeUp} className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
      <div>
        <SectionLabel index={index} className="mb-4">{label}</SectionLabel>
        <h2 className="text-[1.8rem] md:text-[2.4rem] font-normal tracking-tight leading-none text-white">{title}</h2>
      </div>
      {aside}
    </motion.div>
    <motion.div variants={fadeUp}>{children}</motion.div>
  </motion.section>
);

const Field = ({ id, label, type = "text", value, onChange, error, autoComplete }) => (
  <div>
    <label htmlFor={id} className="block text-[10px] font-mono tracking-widest uppercase text-gray-500 mb-2">{label}</label>
    <input
      id={id}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoComplete={autoComplete}
      aria-invalid={Boolean(error)}
      aria-describedby={error ? `${id}-error` : undefined}
      className={`w-full bg-transparent border-b pb-3 text-white text-[15px] outline-none placeholder:text-gray-600 transition-colors ${
        error ? "border-red-400 focus:border-red-400" : "border-gray-700 focus:border-white"
      }`}
    />
    {error && (
      <p id={`${id}-error`} className="mt-2 text-[11px] font-mono tracking-wider uppercase text-red-400">{error}</p>
    )}
  </div>
);

function ProfileForm() {
  const { user, updateProfile } = useAuth();
  const initial = { username: user?.username || "", email: user?.email || "" };
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState(false);

  // Keep the form in sync if the user object changes elsewhere
  useEffect(() => {
    setForm({ username: user?.username || "", email: user?.email || "" });
  }, [user?.username, user?.email]);

  const dirty = form.username.trim() !== initial.username || form.email.trim() !== initial.email;

  const set = (key) => (value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(false);
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const onSubmit = (e) => {
    e.preventDefault();
    const next = validate(form);
    setErrors(next);
    if (Object.keys(next).length) return;
    updateProfile(form);
    setSaved(true);
  };

  const onCancel = () => {
    setForm(initial);
    setErrors({});
    setSaved(false);
  };

  return (
    <Panel glow className="p-8 md:p-10 max-w-[640px]">
      <form onSubmit={onSubmit} noValidate className="space-y-8">
        <Field id="profile-name" label="Display name" value={form.username} onChange={set("username")} error={errors.username} autoComplete="name" />
        <Field id="profile-email" label="Email" type="email" value={form.email} onChange={set("email")} error={errors.email} autoComplete="email" />

        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <PrimaryButton type="submit" icon={Check} disabled={!dirty}>Save changes</PrimaryButton>
          <button
            type="button"
            onClick={onCancel}
            disabled={!dirty}
            className="px-5 py-3 rounded-full border border-gray-600 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <span role="status" className="text-[11px] font-mono tracking-wider uppercase text-green-500">
            {saved && !dirty ? "Saved" : ""}
          </span>
        </div>
      </form>

      <p className="mt-8 pt-6 border-t border-gray-800 text-[10px] font-mono tracking-widest uppercase text-gray-500 leading-relaxed">
        Saved on this device — account sync arrives with sign-in.
      </p>
    </Panel>
  );
}

// Miniature of a page (navbar, heading, two panels) drawn with the theme tokens.
function MiniPage() {
  return (
    <div className="h-full w-full bg-page p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="h-1.5 w-8 rounded-full bg-white" />
        <span className="h-3 w-3 rounded-full border border-gray-600" />
      </div>
      <span className="mt-1 h-2.5 w-2/3 rounded-sm bg-white" />
      <span className="h-1 w-1/3 rounded-full bg-gray-600" />
      <div className="mt-auto grid grid-cols-2 gap-1.5">
        <span className="h-8 rounded-md bg-surface border border-gray-800" />
        <span className="h-8 rounded-md bg-surface border border-gray-800 flex items-end p-1.5">
          <span className="h-1 w-5 rounded-full bg-green-500" />
        </span>
      </div>
    </div>
  );
}

function ThemePreview({ value }) {
  if (value === "system") {
    return (
      <>
        <div className="absolute inset-0 theme-light"><MiniPage /></div>
        <div className="absolute inset-0 theme-dark [clip-path:polygon(100%_0,100%_100%,0_100%)]"><MiniPage /></div>
      </>
    );
  }
  return <div className={`absolute inset-0 theme-${value}`}><MiniPage /></div>;
}

const THEMES = [
  { value: "light", label: "Light", icon: Sun, note: "Off-white canvas, white panels" },
  { value: "dark", label: "Dark", icon: Moon, note: "The original InvestIQ terminal" },
  { value: "system", label: "System", icon: Monitor, note: "Follows your device setting" },
];

function Appearance() {
  const { preference, theme, setPreference } = useTheme();

  return (
    <div role="radiogroup" aria-label="Theme" className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-[900px]">
      {THEMES.map(({ value, label, icon: Icon, note }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setPreference(value)}
            className={`group flex flex-col w-full text-left rounded-xl border bg-surface overflow-hidden transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-gray-400 ${
              active ? "border-white" : "border-gray-800 hover:border-gray-500"
            }`}
          >
            <div aria-hidden="true" className="relative shrink-0 h-32 border-b border-gray-800 overflow-hidden">
              <ThemePreview value={value} />
            </div>
            <div className="flex items-start justify-between gap-3 px-5 py-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-white">
                  <Icon size={14} strokeWidth={1.5} aria-hidden="true" /> {label}
                </div>
                <MonoLabel className="block mt-2 text-gray-500 normal-case tracking-wider">
                  {value === "system" ? `${note} · now ${theme}` : note}
                </MonoLabel>
              </div>
              <span
                aria-hidden="true"
                className={`mt-0.5 w-5 h-5 shrink-0 rounded-full border flex items-center justify-center transition-colors ${
                  active ? "bg-white border-white text-black" : "border-gray-600 text-transparent"
                }`}
              >
                <Check size={12} strokeWidth={2.5} />
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function Account() {
  const { user, logout } = useAuth();
  return (
    <Panel className="max-w-[640px] divide-y divide-gray-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-6 md:px-8 py-6">
        <MonoLabel className="text-gray-500">Signed in as</MonoLabel>
        <span className="text-sm text-white break-all">{user?.email}</span>
      </div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-6 md:px-8 py-6">
        <MonoLabel className="text-gray-500">Session</MonoLabel>
        <button
          type="button"
          onClick={logout}
          className="self-start sm:self-auto flex items-center gap-2 px-5 py-2.5 rounded-full border border-gray-600 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white transition-colors cursor-pointer"
        >
          <LogOut size={14} strokeWidth={1.5} /> Sign out
        </button>
      </div>
    </Panel>
  );
}

export default function Settings() {
  const { hash } = useLocation();

  // Support /settings#profile (e.g. "Edit profile" in the navbar menu)
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    el.scrollIntoView({ block: "start" });
    el.querySelector("input")?.focus({ preventScroll: true });
  }, [hash]);

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-12">
        <PageHeading index="06" label="Account" title="SETTINGS">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[360px] lg:text-right">
            Your profile, how InvestIQ looks, and your session.
          </p>
        </PageHeading>
      </section>

      <Section id="profile" index="01" label="Profile" title="Your details">
        <ProfileForm />
      </Section>

      <Section id="appearance" index="02" label="Appearance" title="Theme">
        <Appearance />
      </Section>

      <Section id="account" index="03" label="Account" title="Session">
        <Account />
      </Section>

      <Footer />
    </div>
  );
}
