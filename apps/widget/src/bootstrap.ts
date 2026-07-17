import { resolveParentOriginFromBootstrap } from "./parent-origin";
import { startIframeHandshake, type IframeHandshakeController } from "./handshake";
import { WidgetBootstrapService, type WidgetRuntimeServices } from "./services/bootstrap-service";
import type { FetchLike } from "./api/client";
import type { ConfigCacheStorage } from "./api/config";
import { WIDGET_SHELL_ROOT_ID } from "./constants";
import { mountWidgetUi } from "./ui/root";
import "./style.css";

export type BootstrapWidgetShellOptions = Readonly<{
  fetchImpl?: FetchLike;
  configStorage?: ConfigCacheStorage;
  apiHostOverride?: string;
  onRuntimeReady?: (runtime: WidgetRuntimeServices) => void;
}>;

export function bootstrapWidgetShell(documentRef: Document = document, windowRef: Window = window, options: BootstrapWidgetShellOptions = {}): void {
  const root = documentRef.getElementById(WIDGET_SHELL_ROOT_ID);
  if (!root) return;

  let controller: IframeHandshakeController | null = null;
  let runtime: WidgetRuntimeServices | null = null;
  const ui = mountWidgetUi(root, {
    onOpen: () => controller?.requestOpenFromUi(),
    onClose: () => controller?.requestCloseFromUi(),
  });

  try {
    const parent = resolveParentOriginFromBootstrap(windowRef.location.href, documentRef.referrer);
    const bootstrapService = new WidgetBootstrapService();
    controller = startIframeHandshake({
      parentOrigin: parent.parentOrigin,
      parentWindow: windowRef.parent,
      selfWindow: windowRef,
      onInitialise: async (payload) => {
        setDocumentLanguage(documentRef, payload.localeHint);
        runtime = await bootstrapService.bootstrap({
          payload,
          windowRef,
          fetchImpl: options.fetchImpl,
          configStorage: options.configStorage,
          apiHostOverride: options.apiHostOverride ?? getTestApiHostOverride(),
        });
        const configLanguage = runtime.stateStore.snapshot().config.data?.widget.language;
        setDocumentLanguage(documentRef, configLanguage ?? payload.localeHint);
        ui.attachStore(runtime.stateStore);
        installTestHarness(windowRef, runtime);
        options.onRuntimeReady?.(runtime);
      },
      onReady: (payload) => ui.setShellState(payload.initialOpen ? "open" : "closed"),
      onOpen: () => ui.setShellState("open"),
      onClose: () => ui.setShellState("closed"),
      onDestroy: () => {
        runtime?.sessionService.destroyInMemory();
        runtime?.stateStore.destroy();
        ui.destroy();
      },
      onError: () => ui.setUnavailable(),
    });
  } catch {
    ui.setUnavailable();
  }
}

function getTestApiHostOverride(): string | undefined {
  if (import.meta.env.MODE === "production") return undefined;
  return import.meta.env.VITE_WIDGET_TEST_API_HOST;
}

function setDocumentLanguage(documentRef: Document, value: string | undefined): void {
  const language = typeof value === "string" && /^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{2,8})?$/.test(value) ? value : "en";
  documentRef.documentElement.lang = language;
}

function installTestHarness(windowRef: Window, runtime: WidgetRuntimeServices): void {
  if (import.meta.env.MODE !== "test") return;
  Object.defineProperty(windowRef, "__yoranixWidgetTestHarness", {
    configurable: true,
    enumerable: false,
    value: Object.freeze({
      state: () => runtime.stateStore.snapshot(),
      sendMessage: (message: string) => runtime.messageService.sendMessage(message),
      destroySensitiveMemory: () => runtime.sessionService.destroyInMemory(),
    }),
  });
}
