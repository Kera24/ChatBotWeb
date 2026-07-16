import type { WidgetSDKConfig } from "../config";
import { createSDKError, WidgetSDKError, type WidgetSDKErrorPublic } from "../errors";
import { SDK_VERSION, WIDGET_PROTOCOL_VERSION } from "../version";
import { WidgetRuntimeController } from "./controller";
import type { WidgetSDKEventHandler, WidgetSDKEventName } from "./events";
import type { WidgetRuntimeState } from "./lifecycle";

export type YoranixWidgetPublicAPI = Readonly<{
  version: string;
  protocolVersion: number;
  init(config?: WidgetSDKConfig): Promise<void>;
  open(): Promise<void>;
  close(): Promise<void>;
  toggle(): Promise<void>;
  destroy(): Promise<void>;
  isOpen(): boolean;
  isReady(): boolean;
  whenReady(): Promise<void>;
  on<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): () => void;
  off<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): void;
  getState(): WidgetRuntimeState;
}>;

type RuntimeSlot = {
  controller?: WidgetRuntimeController;
  configSignature?: string;
};

const runtimeSlot: RuntimeSlot = {};

export function createPublicAPI(windowRef: Window & typeof globalThis = window, documentRef: Document = document): YoranixWidgetPublicAPI {
  const getController = () => {
    if (!runtimeSlot.controller || runtimeSlot.controller.getState() === "destroyed") {
      runtimeSlot.controller = new WidgetRuntimeController(windowRef, documentRef);
      runtimeSlot.configSignature = undefined;
    }
    return runtimeSlot.controller;
  };

  const apiObject: YoranixWidgetPublicAPI = {
    version: SDK_VERSION,
    protocolVersion: WIDGET_PROTOCOL_VERSION,
    async init(config: WidgetSDKConfig = readConfigFromCurrentScript(documentRef)) {
      const signature = safeConfigSignature(config);
      if (runtimeSlot.controller && runtimeSlot.controller.getState() !== "destroyed") {
        if (runtimeSlot.configSignature === signature) {
          return runtimeSlot.controller.whenReady();
        }
        throw createSDKError("duplicate_initialisation", "runtime");
      }
      const controller = getController();
      runtimeSlot.configSignature = signature;
      try {
        await controller.init(config);
      } catch (error) {
        throw projectError(error);
      }
    },
    open() {
      if (!runtimeSlot.controller) return Promise.reject(createSDKError("sdk_not_ready", "runtime").toPublicJSON());
      return runtimeSlot.controller.open().catch((error: unknown) => Promise.reject(projectError(error)));
    },
    close() {
      if (!runtimeSlot.controller) return Promise.reject(createSDKError("sdk_not_ready", "runtime").toPublicJSON());
      return runtimeSlot.controller.close().catch((error: unknown) => Promise.reject(projectError(error)));
    },
    toggle() {
      if (!runtimeSlot.controller) return Promise.reject(createSDKError("sdk_not_ready", "runtime").toPublicJSON());
      return runtimeSlot.controller.toggle().catch((error: unknown) => Promise.reject(projectError(error)));
    },
    async destroy() {
      if (!runtimeSlot.controller) return;
      await runtimeSlot.controller.destroy();
      runtimeSlot.controller = undefined;
      runtimeSlot.configSignature = undefined;
    },
    isOpen() {
      return runtimeSlot.controller?.isOpen() ?? false;
    },
    isReady() {
      return runtimeSlot.controller?.isReady() ?? false;
    },
    whenReady() {
      if (!runtimeSlot.controller) return Promise.reject(createSDKError("sdk_not_ready", "runtime").toPublicJSON());
      return runtimeSlot.controller.whenReady().catch((error: unknown) => Promise.reject(projectError(error)));
    },
    on(event, handler) {
      return getController().on(event, handler);
    },
    off(event, handler) {
      runtimeSlot.controller?.off(event, handler);
    },
    getState() {
      return runtimeSlot.controller?.getState() ?? "uninitialised";
    },
  };
  Object.defineProperty(apiObject, "__yoranixWidgetSdk", { value: true, enumerable: false });
  return Object.freeze(apiObject);
}

export function installGlobalAPI(windowRef: Window & typeof globalThis = window, documentRef: Document = document): boolean {
  const existing = (windowRef as unknown as { YoranixWidget?: unknown }).YoranixWidget;
  if (existing && !isYoranixGlobal(existing)) {
    return false;
  }
  if (existing && isYoranixGlobal(existing)) {
    maybeAutoInit(existing as YoranixWidgetPublicAPI, documentRef);
    return true;
  }
  const api = createPublicAPI(windowRef, documentRef);
  Object.defineProperty(windowRef, "YoranixWidget", {
    value: api,
    configurable: true,
    enumerable: false,
    writable: false,
  });
  maybeAutoInit(api, documentRef);
  return true;
}

export function readConfigFromCurrentScript(documentRef: Document = document): WidgetSDKConfig {
  const script = documentRef.currentScript;
  if (!(script instanceof HTMLScriptElement)) {
    return { widgetKey: "" };
  }
  return readConfigFromScriptElement(script);
}

export function readConfigFromScriptElement(script: HTMLScriptElement): WidgetSDKConfig {
  const config: WidgetSDKConfig = {
    widgetKey: script.dataset.widgetKey ?? "",
  };
  if (script.dataset.environment) config.environment = script.dataset.environment as WidgetSDKConfig["environment"];
  if (script.dataset.initialOpen !== undefined) config.initialOpen = parseBoolean(script.dataset.initialOpen);
  if (script.dataset.mountMode) config.mountMode = script.dataset.mountMode as WidgetSDKConfig["mountMode"];
  if (script.dataset.locale) config.localeHint = script.dataset.locale;
  if (script.dataset.debug !== undefined) config.debug = parseBoolean(script.dataset.debug);
  if (script.dataset.container) config.container = script.dataset.container;
  if (script.nonce) config.nonce = script.nonce;
  return config;
}

function maybeAutoInit(api: YoranixWidgetPublicAPI, documentRef: Document): void {
  const script = documentRef.currentScript;
  if (!(script instanceof HTMLScriptElement) || !script.dataset.widgetKey) {
    return;
  }
  void api.init(readConfigFromScriptElement(script)).catch(() => undefined);
}

function parseBoolean(value: string): boolean {
  return value === "true" || value === "1" || value === "";
}

function isYoranixGlobal(value: unknown): boolean {
  return typeof value === "object" && value !== null && (value as { __yoranixWidgetSdk?: boolean }).__yoranixWidgetSdk === true;
}

function safeConfigSignature(config: WidgetSDKConfig): string {
  return JSON.stringify({
    widgetKey: config.widgetKey,
    environment: config.environment ?? null,
    initialOpen: config.initialOpen ?? false,
    mountMode: config.mountMode ?? "floating",
    localeHint: config.localeHint ?? null,
    debug: config.debug ?? false,
    iframeHost: config.iframeHost ?? null,
    sdkHost: config.sdkHost ?? null,
  });
}

function projectError(error: unknown): WidgetSDKErrorPublic {
  if (error instanceof WidgetSDKError) {
    return error.toPublicJSON();
  }
  return createSDKError("safe_internal_error", "runtime", { cause: error }).toPublicJSON();
}

export function autoInstallGlobalAPI(): void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }
  installGlobalAPI(window, document);
}



