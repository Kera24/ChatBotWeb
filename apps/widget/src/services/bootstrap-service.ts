import type { InitialisePayload } from "@yoranix/widget-sdk";
import { PublicWidgetApiClient, type FetchLike } from "../api/client";
import { resolveWidgetApiEnvironment, WidgetConfigCache, type ConfigCacheStorage } from "../api/config";
import { WidgetApiError, toWidgetApiError } from "../api/errors";
import { createSessionStore } from "../storage";
import type { SessionStore } from "../storage/session-store";
import { WidgetStateStore } from "../state/widget-state";
import { SessionService } from "./session-service";
import { MessageService } from "./message-service";

export type WidgetRuntimeServices = Readonly<{
  apiClient: PublicWidgetApiClient;
  stateStore: WidgetStateStore;
  sessionStore: SessionStore;
  sessionService: SessionService;
  messageService: MessageService;
}>;

export type BootstrapServiceOptions = Readonly<{
  payload: InitialisePayload;
  windowRef: Window;
  fetchImpl?: FetchLike;
  configStorage?: ConfigCacheStorage;
  stateStore?: WidgetStateStore;
}>;

export class WidgetBootstrapService {
  async bootstrap(options: BootstrapServiceOptions): Promise<WidgetRuntimeServices> {
    const environment = resolveWidgetApiEnvironment(options.payload.environment);
    const apiClient = new PublicWidgetApiClient({
      apiBaseUrl: environment.apiHost,
      widgetKey: options.payload.widgetKey,
      fetchImpl: options.fetchImpl,
    });
    const stateStore = options.stateStore ?? new WidgetStateStore();
    const configStorage = options.configStorage ?? options.windowRef.sessionStorage;
    const configCache = new WidgetConfigCache(configStorage, {
      widgetKey: options.payload.widgetKey,
      environment: options.payload.environment,
    });
    const sessionStore = createSessionStore(options.windowRef, {
      widgetKey: options.payload.widgetKey,
      environment: options.payload.environment,
    });

    stateStore.update({ config: { status: "loading" } });
    try {
      const cached = configCache.get();
      const configResult = await apiClient.getConfig(cached?.etag ?? null);
      const config = configResult.status === 304
        ? cached?.config
        : configResult.config;
      if (!config) {
        throw new WidgetApiError("configuration_unavailable", "configuration", { retryable: true });
      }
      if (configResult.status === 200) {
        configCache.set(config, configResult.etag);
      }
      stateStore.update({
        bootstrapStatus: "ready",
        config: { status: "ready", data: config, etag: configResult.status === 304 ? cached?.etag ?? null : configResult.etag },
      });
      const sessionService = new SessionService({ apiClient, sessionStore, stateStore, configurationVersion: config.configuration_version });
      sessionService.restoreStoredSession();
      const messageService = new MessageService({ apiClient, sessionService, stateStore });
      return Object.freeze({ apiClient, stateStore, sessionStore, sessionService, messageService });
    } catch (error) {
      const safe = toWidgetApiError(error, "configuration");
      stateStore.update({ bootstrapStatus: "unavailable", config: { status: "unavailable" }, lastError: safe.toSafeShape() });
      throw safe;
    }
  }
}