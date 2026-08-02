import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getDashboardApiBaseUrl } from "../api/client";
import type { ApiEnvelope } from "../api/types";
import { dashboardSessionFromAuthContext, type AuthContext, type DashboardSession } from "./development-session";

export async function getServerAuthContext(): Promise<AuthContext | null> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  if (!cookieHeader) return null;

  const response = await fetch(`${getDashboardApiBaseUrl()}/api/v1/auth/me`, {
    headers: { Accept: "application/json", Cookie: cookieHeader },
    cache: "no-store",
  });
  if (!response.ok) return null;
  const payload = (await response.json()) as ApiEnvelope<AuthContext>;
  return payload.data;
}

export async function requireDashboardSession(options: { requireOnboarding?: boolean } = {}): Promise<DashboardSession> {
  const context = await getServerAuthContext();
  if (!context) redirect("/login");
  if (!context.onboarding_complete && options.requireOnboarding !== false) redirect("/onboarding");
  if (context.onboarding_complete && options.requireOnboarding === false) redirect("/dashboard");
  return dashboardSessionFromAuthContext(context);
}
