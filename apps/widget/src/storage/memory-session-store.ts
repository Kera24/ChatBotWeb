import type { StoredSessionRecord } from "../api/contracts";
import { sessionStorageKey, type SessionStore } from "./session-store";

export class MemorySessionStore implements SessionStore {
  private readonly key: string;
  private record: StoredSessionRecord | null = null;

  constructor(scope: { widgetKey: string; environment: string }) {
    this.key = sessionStorageKey(scope.widgetKey, scope.environment);
  }

  get(): StoredSessionRecord | null {
    return this.record ? Object.freeze({ ...this.record }) : null;
  }

  set(record: StoredSessionRecord): void {
    this.record = Object.freeze({ ...record });
  }

  clear(): void {
    this.record = null;
  }

  isAvailable(): boolean {
    return true;
  }

  getKeyForTests(): string {
    return this.key;
  }
}