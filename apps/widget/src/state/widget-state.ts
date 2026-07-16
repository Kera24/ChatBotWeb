import type { PublicMessageResponse, PublicWidgetConfigResponse } from "../api/contracts";
import type { SafeWidgetApiErrorShape } from "../api/errors";

export type ConfigStatus = "idle" | "loading" | "ready" | "unavailable";
export type SessionStatus = "none" | "creating" | "active" | "expired" | "invalid" | "rate_limited" | "unavailable";
export type MessageStatus = "idle" | "sending" | "sent" | "failed" | "request_in_progress";

export type WidgetStateSnapshot = Readonly<{
  bootstrapStatus: "booting" | "ready" | "unavailable" | "destroyed";
  config: Readonly<{
    status: ConfigStatus;
    data: PublicWidgetConfigResponse | null;
    etag: string | null;
  }>;
  session: Readonly<{
    status: SessionStatus;
    expiresAt: string | null;
    absoluteExpiresAt: string | null;
    remainingMessages: number | null;
    configurationVersion: number | null;
  }>;
  message: Readonly<{
    status: MessageStatus;
    lastResponse: PublicMessageResponse | null;
  }>;
  lastError: SafeWidgetApiErrorShape | null;
}>;

export type WidgetStateListener = (snapshot: WidgetStateSnapshot) => void;
export type WidgetStatePatch = Partial<Omit<WidgetStateSnapshot, "config" | "session" | "message">> & {
  config?: Partial<WidgetStateSnapshot["config"]>;
  session?: Partial<WidgetStateSnapshot["session"]>;
  message?: Partial<WidgetStateSnapshot["message"]>;
};

const INITIAL_STATE: WidgetStateSnapshot = Object.freeze({
  bootstrapStatus: "booting",
  config: Object.freeze({ status: "idle", data: null, etag: null }),
  session: Object.freeze({ status: "none", expiresAt: null, absoluteExpiresAt: null, remainingMessages: null, configurationVersion: null }),
  message: Object.freeze({ status: "idle", lastResponse: null }),
  lastError: null,
});

export class WidgetStateStore {
  private snapshotValue: WidgetStateSnapshot = INITIAL_STATE;
  private readonly listeners = new Set<WidgetStateListener>();

  snapshot(): WidgetStateSnapshot {
    return this.snapshotValue;
  }

  subscribe(listener: WidgetStateListener): () => void {
    this.listeners.add(listener);
    listener(this.snapshotValue);
    return () => this.listeners.delete(listener);
  }

  update(patch: WidgetStatePatch): WidgetStateSnapshot {
    this.snapshotValue = Object.freeze({
      ...this.snapshotValue,
      ...patch,
      config: Object.freeze({ ...this.snapshotValue.config, ...(patch.config ?? {}) }),
      session: Object.freeze({ ...this.snapshotValue.session, ...(patch.session ?? {}) }),
      message: Object.freeze({ ...this.snapshotValue.message, ...(patch.message ?? {}) }),
    });
    for (const listener of [...this.listeners]) {
      queueMicrotask(() => listener(this.snapshotValue));
    }
    return this.snapshotValue;
  }

  destroy(): void {
    this.listeners.clear();
    this.update({ bootstrapStatus: "destroyed" });
  }
}