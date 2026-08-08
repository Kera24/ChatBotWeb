"use client";

import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, Check, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";

import { AuthApiError, completeOnboarding, loginAccount, registerAccount, requestPasswordReset, resetPassword, verifyEmail } from "../../lib/api/auth";

type AuthShellProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
};

export function AuthShell({ title, subtitle, children }: AuthShellProps) {
  const reduceMotion = useReducedMotion();
  return (
    <main className="authPage">
      <motion.section className="authPanel" initial={{ opacity: 0, y: reduceMotion ? 0 : 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.36 }}>
        <Link className="authBrand" href="/">
          <Image src="/brand/conversa-icon.svg" alt="" width={38} height={38} aria-hidden="true" />
          <span>Conversa</span>
        </Link>
        <div className="authHeader">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        {children}
      </motion.section>
      <aside className="authPreview" aria-hidden="true">
        <div className="authPreviewCard">
          <span>AI Knowledge Platform</span>
          <strong>Secure access to source-grounded assistants</strong>
          <div><Check size={16} /> Tenant isolation</div>
          <div><Check size={16} /> Role based access</div>
          <div><Check size={16} /> Audit-ready workflows</div>
        </div>
      </aside>
    </main>
  );
}

export function RegisterForm() {
  const router = useRouter();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm_password: "", organisation_name: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const validation = validateRegistration(form);
  const strength = passwordStrength(form.password);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validation) { setError(validation); return; }
    setPending(true);
    setError(null);
    try {
      const response = await registerAccount(form);
      router.push(response.data.onboarding_complete ? "/dashboard" : "/onboarding");
      router.refresh();
    } catch (caught) {
      setError(messageForAuthError(caught, "Registration failed. Check your details and try again."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="authForm" onSubmit={submit} noValidate>
      {error ? <p className="authError" role="alert">{error}</p> : null}
      <AuthInput icon={<UserRound size={17} />} label="Full name" value={form.full_name} onChange={(value) => setForm({ ...form, full_name: value })} autoComplete="name" />
      <AuthInput icon={<Mail size={17} />} label="Work email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} autoComplete="email" type="email" />
      <AuthInput icon={<UserRound size={17} />} label="Organisation name" value={form.organisation_name} onChange={(value) => setForm({ ...form, organisation_name: value })} autoComplete="organization" />
      <AuthInput icon={<LockKeyhole size={17} />} label="Password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} autoComplete="new-password" type={showPassword ? "text" : "password"} action={<button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>} />
      <PasswordStrength score={strength} />
      <AuthInput icon={<LockKeyhole size={17} />} label="Confirm password" value={form.confirm_password} onChange={(value) => setForm({ ...form, confirm_password: value })} autoComplete="new-password" type="password" />
      <button className="authSubmit" type="submit" disabled={pending}>{pending ? "Creating account" : "Create account"} <ArrowRight size={18} /></button>
      <p className="authSwitch">Already have an account? <Link href="/login">Log in</Link></p>
    </form>
  );
}

export function LoginForm() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", remember: false });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await loginAccount(form);
      router.push(response.data.onboarding_complete ? "/dashboard" : "/onboarding");
      router.refresh();
    } catch (caught) {
      setError(messageForAuthError(caught, "Unable to log in. Try again."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="authForm" onSubmit={submit} noValidate>
      {error ? <p className="authError" role="alert">{error}</p> : null}
      <AuthInput icon={<Mail size={17} />} label="Work email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} autoComplete="email" type="email" />
      <AuthInput icon={<LockKeyhole size={17} />} label="Password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} autoComplete="current-password" type="password" />
      <label className="authCheckbox"><input type="checkbox" checked={form.remember} onChange={(event) => setForm({ ...form, remember: event.currentTarget.checked })} /> Remember me on this device</label>
      <button className="authSubmit" type="submit" disabled={pending}>{pending ? "Logging in" : "Log in"} <ArrowRight size={18} /></button>
      <div className="authFormLinks"><Link href="/forgot-password">Forgot password?</Link><Link href="/register">Create account</Link></div>
    </form>
  );
}

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await requestPasswordReset(email);
      setNotice(response.data.message);
    } catch (caught) {
      setError(messageForAuthError(caught, "Password reset request failed."));
    } finally {
      setPending(false);
    }
  }

  return <form className="authForm" onSubmit={submit}>{notice ? <p className="authNotice" role="status">{notice}</p> : null}{error ? <p className="authError" role="alert">{error}</p> : null}<AuthInput icon={<Mail size={17} />} label="Work email" value={email} onChange={setEmail} autoComplete="email" type="email" /><button className="authSubmit" disabled={pending}>{pending ? "Sending" : "Request reset"}</button><p className="authSwitch"><Link href="/login">Back to login</Link></p></form>;
}

export function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [form, setForm] = useState({ password: "", confirm_password: "" });
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await resetPassword(token, form.password, form.confirm_password);
      setMessage(response.data.message);
    } catch (caught) {
      setError(messageForAuthError(caught, "Password reset failed."));
    } finally {
      setPending(false);
    }
  }

  return <form className="authForm" onSubmit={submit}>{message ? <p className="authNotice" role="status">{message}</p> : null}{error ? <p className="authError" role="alert">{error}</p> : null}<AuthInput icon={<LockKeyhole size={17} />} label="New password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} type="password" autoComplete="new-password" /><AuthInput icon={<LockKeyhole size={17} />} label="Confirm password" value={form.confirm_password} onChange={(value) => setForm({ ...form, confirm_password: value })} type="password" autoComplete="new-password" /><button className="authSubmit" disabled={pending || !token}>{pending ? "Updating" : "Reset password"}</button><p className="authSwitch"><Link href="/login">Back to login</Link></p></form>;
}

export function VerifyEmailForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [status, setStatus] = useState<"pending" | "success" | "error">(token ? "pending" : "error");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setMessage("This verification link is missing its token.");
      return;
    }
    let cancelled = false;
    verifyEmail(token)
      .then((response) => {
        if (cancelled) return;
        setStatus("success");
        setMessage(response.data.message);
      })
      .catch((caught) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(messageForAuthError(caught, "Email verification failed."));
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="authForm">
      {status === "pending" ? <p className="authNotice" role="status">Verifying your email…</p> : null}
      {status === "success" ? <p className="authNotice" role="status">{message}</p> : null}
      {status === "error" ? <p className="authError" role="alert">{message}</p> : null}
      <Link className="authSubmit" href="/login">Back to login</Link>
    </div>
  );
}

export function OnboardingPanel() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function continueToDashboard() {
    setPending(true);
    setError(null);
    try {
      await completeOnboarding();
      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(messageForAuthError(caught, "Onboarding could not be completed."));
    } finally {
      setPending(false);
    }
  }

  return <div className="authForm">{error ? <p className="authError" role="alert">{error}</p> : null}<ul className="onboardingList"><li><Check size={16} /> Account created</li><li><Check size={16} /> Organisation provisioned</li><li><Check size={16} /> Workspace ready</li></ul><button className="authSubmit" type="button" disabled={pending} onClick={continueToDashboard}>{pending ? "Opening dashboard" : "Continue to dashboard"}</button></div>;
}

function AuthInput({ label, value, onChange, icon, action, type = "text", autoComplete }: { label: string; value: string; onChange: (value: string) => void; icon: ReactNode; action?: ReactNode; type?: string; autoComplete?: string }) {
  const id = useMemo(() => label.toLowerCase().replace(/\s+/g, "-"), [label]);
  return <label className="authField" htmlFor={id}><span>{label}</span><div>{icon}<input id={id} value={value} onChange={(event) => onChange(event.currentTarget.value)} type={type} autoComplete={autoComplete} />{action}</div></label>;
}

function PasswordStrength({ score }: { score: number }) {
  const labels = ["Use at least 12 characters with uppercase, lowercase, and a number.", "Weak password", "Fair password", "Strong password", "Excellent password"];
  return <div className="passwordStrength" aria-live="polite"><span data-active={score >= 1} /><span data-active={score >= 2} /><span data-active={score >= 3} /><span data-active={score >= 4} /><p>{labels[score]}</p></div>;
}

function passwordStrength(password: string) {
  let score = 0;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return score;
}

function validateRegistration(form: { full_name: string; email: string; password: string; confirm_password: string; organisation_name: string }) {
  if (form.full_name.trim().length < 2) return "Enter your full name.";
  if (!form.email.includes("@")) return "Enter a valid work email.";
  if (form.organisation_name.trim().length < 2) return "Enter your organisation name.";
  if (form.password.length < 12) return "Password must be at least 12 characters.";
  if (form.password !== form.confirm_password) return "Passwords do not match.";
  return null;
}

function messageForAuthError(error: unknown, fallback: string) {
  if (error instanceof AuthApiError) return error.message;
  return fallback;
}

