import type { StoredSessionRecord } from "../api/contracts";
import { validateStoredSessionRecord } from "../security/public-response-validation";
import { sessionStorageKey, type SessionStore } from "./session-store";

export class BrowserSessionStore implements SessionStore {
  private readonly key: string;

  constructor(private readonly storage: Storage, scope: { widgetKey: string; environment: string }) {
    this.key = sessionStorageKey(scope.widgetKey, scope.environment);
  }

  get(): StoredSessionRecord | null {
    try {
      const raw = this.storage.getItem(this.key);
      if (!raw) return null;
      return validateStoredSessionRecord(JSON.parse(raw));
    } catch {
      this.clear();
      return null;
    }
  }

  set(record: StoredSessionRecord): void {
    this.storage.setItem(this.key, JSON.stringify(record));
  }

  clear(): void {
    try {
      this.storage.removeItem(this.key);
    } catch {
      // Storage cleanup is best-effort when the browser blocks access.
    }
  }

  isAvailable(): boolean {
    try {
      const testKey = `${this.key}:probe`;
      this.storage.setItem(testKey, "1");
      this.storage.removeItem(testKey);
      return true;
    } catch {
      return false;
    }
  }
}