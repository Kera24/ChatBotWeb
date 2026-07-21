export type ApiErrorKind =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "network"
  | "server"
  | "unknown";

export class DashboardApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly detail?: unknown;

  constructor(kind: ApiErrorKind, message: string, options: { status?: number; detail?: unknown } = {}) {
    super(message);
    this.name = "DashboardApiError";
    this.kind = kind;
    this.status = options.status;
    this.detail = options.detail;
  }
}

export function apiErrorKindFromStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

export function messageForApiError(error: DashboardApiError): string {
  switch (error.kind) {
    case "unauthorized":
      return "The development dashboard session is unavailable.";
    case "forbidden":
      return "This development user does not have access to the selected workspace.";
    case "not_found":
      return "The requested conversation was not found in the current workspace.";
    case "validation":
      return "The tenant or filter request is invalid.";
    case "conflict":
      return "The request conflicts with the current workspace state.";
    case "network":
      return "The API could not be reached. Check that the local backend is running.";
    case "server":
      return "The API returned a server error.";
    default:
      return error.message || "An unknown API error occurred.";
  }
}

export function isDashboardApiError(error: unknown): error is DashboardApiError {
  return error instanceof DashboardApiError;
}
