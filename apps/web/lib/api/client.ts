import { developmentDashboardHeaders, type DevelopmentDashboardSession } from "../auth/development-session";
import { DashboardApiError, apiErrorKindFromStatus } from "./errors";
import type { ApiEnvelope } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getDashboardApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

type DashboardApiRequest = {
  path: string;
  session: DevelopmentDashboardSession;
  searchParams?: Record<string, string | number | undefined | null>;
  cache?: RequestCache;
};

export async function dashboardApiGet<TData, TMeta = Record<string, unknown>>({
  path,
  session,
  searchParams,
  cache = "no-store",
}: DashboardApiRequest): Promise<ApiEnvelope<TData, TMeta>> {
  const url = new URL(`${getDashboardApiBaseUrl()}${path}`);
  for (const [key, value] of Object.entries(searchParams ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...developmentDashboardHeaders(session),
      },
      cache,
    });
  } catch (error) {
    throw new DashboardApiError("network", "Network failure while calling dashboard API.", { detail: error });
  }

  const payload = await readPayload(response);
  if (!response.ok) {
    throw new DashboardApiError(apiErrorKindFromStatus(response.status), "Dashboard API request failed.", {
      status: response.status,
      detail: payload,
    });
  }

  return payload as ApiEnvelope<TData, TMeta>;
}

async function readPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}
