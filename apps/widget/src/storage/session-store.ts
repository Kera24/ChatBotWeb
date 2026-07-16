import type { StoredSessionRecord } from "../api/contracts";

export interface SessionStore {
  get(): StoredSessionRecord | null;
  set(record: StoredSessionRecord): void;
  clear(): void;
  isAvailable(): boolean;
}

export function sessionStorageKey(widgetKey: string, environment: string): string {
  return `yoranix:widget-session:${environment}:${widgetKey}`;
}