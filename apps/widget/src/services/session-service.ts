import type { PublicSessionResponse, StoredSessionRecord } from "../api/contracts";
import { STORED_SESSION_SCHEMA_VERSION } from "../api/contracts";
import type { PublicWidgetApiClient } from "../api/client";
import { WidgetApiError, toWidgetApiError } from "../api/errors";
import type { SessionStore } from "../storage/session-store";
import type { WidgetStateStore } from "../state/widget-state";

export type SessionServiceOptions = Readonly<{
  apiClient: PublicWidgetApiClient;
  sessionStore: SessionStore;
  stateStore: WidgetStateStore;
  configurationVersion: number;
}>;

export class SessionService {
  private createPromise: Promise<StoredSessionRecord> | null = null;
  private inMemorySession: StoredSessionRecord | null = null;

  constructor(private readonly options: SessionServiceOptions) {}

  restoreStoredSession(now = new Date()): StoredSessionRecord | null {
    const record = this.options.sessionStore.get();
    if (!record || this.isExpired(record, now) || record.configurationVersion !== this.options.configurationVersion) {
      this.clear("none");
      return null;
    }
    this.inMemorySession = record;
    this.publishActive(record);
    return record;
  }

  getActiveSession(now = new Date()): StoredSessionRecord | null {
    const record = this.inMemorySession ?? this.restoreStoredSession(now);
    if (!record || this.isExpired(record, now)) {
      this.clear("expired");
      return null;
    }
    return record;
  }

  async ensureSession(): Promise<StoredSessionRecord> {
    const existing = this.getActiveSession();
    if (existing) return existing;
    if (this.createPromise) return this.createPromise;
    this.options.stateStore.update({ session: { status: "creating" } });
    this.createPromise = this.options.apiClient.createSession()
      .then((response) => this.persistSessionResponse(response))
      .catch((error) => {
        const safe = toWidgetApiError(error, "session");
        const status = safe.code === "rate_limited" ? "rate_limited" : "unavailable";
        this.options.stateStore.update({ session: { status }, lastError: safe.toSafeShape() });
        throw safe;
      })
      .finally(() => {
        this.createPromise = null;
      });
    return this.createPromise;
  }

  updateFromMessage(remainingMessages: number, expiresAt: string): void {
    const current = this.inMemorySession ?? this.options.sessionStore.get();
    if (!current) return;
    const updated: StoredSessionRecord = Object.freeze({ ...current, remainingMessages, expiresAt });
    this.inMemorySession = updated;
    this.options.sessionStore.set(updated);
    this.publishActive(updated);
  }

  clear(status: "none" | "expired" | "invalid" = "none"): void {
    this.inMemorySession = null;
    this.options.sessionStore.clear();
    this.options.stateStore.update({
      session: { status, expiresAt: null, absoluteExpiresAt: null, remainingMessages: null, configurationVersion: null },
    });
  }

  destroyInMemory(): void {
    this.inMemorySession = null;
    this.createPromise = null;
  }

  private persistSessionResponse(response: PublicSessionResponse): StoredSessionRecord {
    const record: StoredSessionRecord = Object.freeze({
      sessionToken: response.session_token,
      expiresAt: response.expires_at,
      absoluteExpiresAt: response.absolute_expires_at,
      remainingMessages: response.remaining_messages,
      configurationVersion: response.configuration_version,
      createdAt: new Date().toISOString(),
      schemaVersion: STORED_SESSION_SCHEMA_VERSION,
    });
    this.inMemorySession = record;
    this.options.sessionStore.set(record);
    this.publishActive(record);
    return record;
  }

  private publishActive(record: StoredSessionRecord): void {
    this.options.stateStore.update({
      session: {
        status: "active",
        expiresAt: record.expiresAt,
        absoluteExpiresAt: record.absoluteExpiresAt,
        remainingMessages: record.remainingMessages,
        configurationVersion: record.configurationVersion,
      },
    });
  }

  private isExpired(record: StoredSessionRecord, now: Date): boolean {
    return Date.parse(record.expiresAt) <= now.getTime() || Date.parse(record.absoluteExpiresAt) <= now.getTime();
  }
}