import { getDashboardApiBaseUrl } from "./client";
import type { ApiEnvelope } from "./types";
import type { AuthContext } from "../auth/development-session";

export type AuthErrorKind = "duplicate" | "invalid" | "inactive" | "rate_limited" | "unknown";

export class AuthApiError extends Error {
  kind: AuthErrorKind;
  status?: number;

  constructor(kind: AuthErrorKind, message: string, status?: number) {
    super(message);
    this.name = "AuthApiError";
    this.kind = kind;
    this.status = status;
  }
}

export type RegisterPayload = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  organisation_name: string;
};

export type LoginPayload = {
  email: string;
  password: string;
  remember: boolean;
};

async function authRequest<T>(path: string, body?: Record<string, unknown>) {
  const response = await fetch(`${getDashboardApiBaseUrl()}${path}`, {
    method: body ? "POST" : "GET",
    headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
    cache: "no-store",
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "Authentication request failed.";
    const kind: AuthErrorKind = response.status === 409 ? "duplicate" : response.status === 401 ? "invalid" : response.status === 403 ? "inactive" : response.status === 429 ? "rate_limited" : "unknown";
    throw new AuthApiError(kind, detail, response.status);
  }
  return payload as ApiEnvelope<T>;
}

export function registerAccount(payload: RegisterPayload) {
  return authRequest<AuthContext>("/api/v1/auth/register", payload);
}

export function loginAccount(payload: LoginPayload) {
  return authRequest<AuthContext>("/api/v1/auth/login", payload);
}

export function logoutAccount() {
  return authRequest<{ message: string }>("/api/v1/auth/logout", {});
}

export function requestPasswordReset(email: string) {
  return authRequest<{ message: string; reset_delivery_supported: boolean }>("/api/v1/auth/forgot-password", { email });
}

export function resetPassword(token: string, password: string, confirm_password: string) {
  return authRequest<{ message: string }>("/api/v1/auth/reset-password", { token, password, confirm_password });
}

export function completeOnboarding() {
  return authRequest<AuthContext>("/api/v1/auth/onboarding/complete", {});
}
