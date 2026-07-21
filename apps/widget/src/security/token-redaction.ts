export function redactPublicKey(value: string): string {
  if (value.length <= 10) {
    return "[redacted]";
  }
  return `${value.slice(0, 7)}...[redacted]`;
}

export function containsSessionToken(value: unknown): boolean {
  if (typeof value === "string") {
    return /pss_(dev|stg|live)_[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/.test(value);
  }
  if (Array.isArray(value)) {
    return value.some((entry) => containsSessionToken(entry));
  }
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).some((entry) => containsSessionToken(entry));
  }
  return false;
}

export function assertNoSessionToken(value: unknown): void {
  if (containsSessionToken(value)) {
    throw new Error("session token leaked across public boundary");
  }
}
