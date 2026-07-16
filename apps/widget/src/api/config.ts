import { type WidgetEnvironment, normaliseHostUrl, resolveWidgetEnvironment } from "@yoranix/widget-sdk";
import type { CachedConfigRecord, PublicWidgetConfigResponse } from "./contracts";
import { WidgetApiError } from "./errors";
import { validateCachedConfigRecord } from "../security/public-response-validation";

export type ResolvedWidgetApiEnvironment = Readonly<{
  environment: WidgetEnvironment;
  apiHost: string;
}>;

export function resolveWidgetApiEnvironment(environment: WidgetEnvironment, apiHostOverride?: string): ResolvedWidgetApiEnvironment {
  if (apiHostOverride && environment !== "development") {
    throw new WidgetApiError("safe_internal_error", "configuration", { retryable: false });
  }
  const resolved = resolveWidgetEnvironment(environment);
  if (resolved instanceof Error) {
    throw new WidgetApiError("safe_internal_error", "configuration", { retryable: false });
  }
  const host = apiHostOverride ?? resolved.apiHost;
  const normalised = normaliseHostUrl(host, environment);
  if (typeof normalised !== "string") {
    throw new WidgetApiError("safe_internal_error", "configuration", { retryable: false });
  }
  return Object.freeze({ environment, apiHost: normalised });
}

export interface ConfigCacheStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export class WidgetConfigCache {
  constructor(
    private readonly storage: ConfigCacheStorage,
    private readonly scope: { widgetKey: string; environment: WidgetEnvironment },
  ) {}

  get(): CachedConfigRecord | null {
    const raw = this.storage.getItem(this.key());
    if (!raw) return null;
    try {
      return validateCachedConfigRecord(JSON.parse(raw));
    } catch {
      this.clear();
      return null;
    }
  }

  set(config: PublicWidgetConfigResponse, etag: string | null): void {
    const record: CachedConfigRecord = Object.freeze({
      schemaVersion: "1.0",
      etag,
      cachedAt: new Date().toISOString(),
      config,
    });
    this.storage.setItem(this.key(), JSON.stringify(record));
  }

  clear(): void {
    this.storage.removeItem(this.key());
  }

  private key(): string {
    return `yoranix:widget-config:${this.scope.environment}:${this.scope.widgetKey}`;
  }
}