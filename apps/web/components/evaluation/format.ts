export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a";
  return `${Math.round(value)} ms`;
}

export function formatCategory(value: string): string {
  return value.replace(/_/g, " ");
}

export function toneForCase(passed: boolean, hardFailure: boolean): string {
  if (hardFailure) return "failed";
  if (!passed) return "fallback";
  return "answered";
}

export function toneForGate(passed: boolean): string {
  return passed ? "answered" : "failed";
}

export function toneForRunStatus(status: string): string {
  if (status === "completed") return "completed";
  if (status === "pending" || status === "running") return "pending";
  return "failed";
}
