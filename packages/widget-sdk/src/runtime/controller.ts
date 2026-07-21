import { assertValidWidgetSDKConfig, type ValidatedWidgetSDKConfig, type WidgetSDKConfig } from "../config";
import { createSDKError, WidgetSDKError } from "../errors";
import { buildInitialisePayload, SDKHandshakeController } from "../handshake";
import { buildWidgetIframeUrl, type BuiltIframeUrl } from "../iframe";
import {
  createProtocolEnvelope,
  RecentMessageTracker,
  validateProtocolEnvelope,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
  type WidgetProtocolEnvelope,
} from "../protocol";
import { SDK_VERSION } from "../version";
import { createDebugLogger, type DebugLogger } from "./debug";
import { hasDocumentBody, mountIframe, removeMountedFrame, setContainerOpen, type MountedWidgetFrame } from "./dom";
import { WidgetEventEmitter } from "./events";
import type { WidgetSDKEventHandler, WidgetSDKEventName } from "./events";
import { FocusManager } from "./focus";
import { WidgetLifecycle, type WidgetRuntimeState } from "./lifecycle";
import { createDeferred, type Deferred } from "./readiness";
import { applyResize } from "./resize";
import { attachVisibilityNotifier, type VisibilityNotifier } from "./visibility";

const COMMAND_TIMEOUT_MS = 3000;

type RuntimeWindow = Window & typeof globalThis;

type PendingCommand = {
  expectedState: "ready_open" | "ready_closed";
  resolve(): void;
  reject(error: WidgetSDKError): void;
  timer: ReturnType<typeof setTimeout>;
};

export class WidgetRuntimeController {
  private readonly lifecycle = new WidgetLifecycle();
  private readonly events = new WidgetEventEmitter();
  private readonly readyDeferred: Deferred<void> = createDeferred<void>();
  private readonly focus = new FocusManager();
  private readonly recentMessages = new RecentMessageTracker();
  private frame?: MountedWidgetFrame;
  private builtUrl?: BuiltIframeUrl;
  private config?: ValidatedWidgetSDKConfig;
  private handshake?: SDKHandshakeController;
  private visibility?: VisibilityNotifier;
  private logger?: DebugLogger;
  private pendingCommand?: PendingCommand;
  private initSignature?: string;
  private mountedListener = false;

  constructor(private readonly windowRef: RuntimeWindow = window, private readonly documentRef: Document = document) {}

  async init(input: WidgetSDKConfig): Promise<void> {
    if (this.lifecycle.state === "destroying") {
      throw createSDKError("destroyed", "runtime");
    }
    if (this.lifecycle.state !== "uninitialised" && this.lifecycle.state !== "destroyed") {
      const nextSignature = this.signatureForInput(input);
      if (this.initSignature && nextSignature === this.initSignature) {
        return this.whenReady();
      }
      throw createSDKError("duplicate_initialisation", "runtime");
    }
    try {
      this.lifecycle.transition("validating");
      const config = assertValidWidgetSDKConfig(input);
      this.config = config;
      this.initSignature = this.signatureForConfig(config);
      this.logger = createDebugLogger(config);
      await this.waitForBody();
      if (!hasDocumentBody(this.documentRef)) {
        throw createSDKError("dom_unavailable", "bootstrap", { retryable: true });
      }
      const builtUrl = buildWidgetIframeUrl(config, this.windowRef.location.origin);
      if (builtUrl instanceof WidgetSDKError) {
        throw builtUrl;
      }
      this.builtUrl = builtUrl;
      this.lifecycle.transition("mounting");
      this.frame = mountIframe(this.documentRef, config, builtUrl);
      this.frame.iframe.addEventListener("error", this.handleIframeError, { once: true });
      this.lifecycle.transition("handshaking");
      this.events.emit("state_changed", { state: this.lifecycle.state });
      const iframeWindow = this.frame.iframe.contentWindow;
      if (!iframeWindow) {
        throw createSDKError("iframe_load_failed", "iframe", { retryable: true });
      }
      this.handshake = new SDKHandshakeController({
        iframeWindow,
        iframeOrigin: builtUrl.iframeOrigin,
        parentWindow: this.windowRef,
        initialisePayload: buildInitialisePayload({
          widgetKey: config.widgetKey,
          parentOrigin: builtUrl.parentOrigin,
          sdkVersion: SDK_VERSION,
          environment: config.environment,
          initialOpen: config.initialOpen,
          mountMode: config.mountMode,
          ...(config.localeHint ? { localeHint: config.localeHint } : {}),
          debug: config.debug,
        }),
        onReady: () => this.handleHandshakeReady(),
        onError: (error) => this.fail(error instanceof WidgetSDKError ? error : createSDKError("protocol_mismatch", "protocol")),
      });
      this.handshake.start();
      return this.whenReady();
    } catch (error) {
      const sdkError = error instanceof WidgetSDKError ? error : createSDKError("safe_internal_error", "runtime", { cause: error });
      this.fail(sdkError);
      throw sdkError;
    }
  }

  async open(): Promise<void> {
    this.focus.remember(this.documentRef);
    await this.sendStateCommand("open", "ready_open");
    if (this.frame) {
      this.focus.focusIframe(this.frame.iframe);
    }
  }

  async close(): Promise<void> {
    await this.sendStateCommand("close", "ready_closed");
    this.focus.restore();
  }

  async toggle(): Promise<void> {
    return this.isOpen() ? this.close() : this.open();
  }

  async destroy(): Promise<void> {
    if (this.lifecycle.state === "destroyed") return;
    if (this.lifecycle.state !== "destroying") {
      try {
        this.lifecycle.transition("destroying");
      } catch {
        this.lifecycle.state = "destroying";
      }
    }
    this.sendFireAndForget("destroy", {});
    this.clearPendingCommand(createSDKError("destroyed", "runtime"));
    this.visibility?.detach();
    this.visibility = undefined;
    this.windowRef.removeEventListener("message", this.handleRuntimeMessage);
    this.windowRef.removeEventListener("resize", this.handleViewportResize);
    this.mountedListener = false;
    this.handshake?.destroy();
    this.handshake = undefined;
    removeMountedFrame(this.frame);
    this.frame = undefined;
    this.events.emit("destroyed", { state: "destroyed" });
    this.events.clear();
    this.readyDeferred.reject(createSDKError("destroyed", "runtime"));
    this.lifecycle.transition("destroyed");
    this.config = undefined;
    this.builtUrl = undefined;
    this.initSignature = undefined;
  }

  isOpen(): boolean {
    return this.lifecycle.isOpen();
  }

  isReady(): boolean {
    return this.lifecycle.isReady();
  }

  getState(): WidgetRuntimeState {
    return this.lifecycle.state;
  }

  whenReady(): Promise<void> {
    return this.readyDeferred.promise;
  }

  on<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): () => void {
    return this.events.on(event, handler);
  }

  off<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): void {
    this.events.off(event, handler);
  }

  private handleHandshakeReady(): void {
    if (!this.frame || !this.builtUrl) return;
    const nextState = this.config?.initialOpen ? "ready_open" : "ready_closed";
    this.lifecycle.transition(nextState);
    setContainerOpen(this.frame.container, nextState === "ready_open");
    if (!this.mountedListener) {
      this.windowRef.addEventListener("message", this.handleRuntimeMessage);
      this.windowRef.addEventListener("resize", this.handleViewportResize);
      this.mountedListener = true;
    }
    const iframeWindow = this.frame.iframe.contentWindow;
    if (iframeWindow) {
      this.visibility = attachVisibilityNotifier(this.documentRef, iframeWindow, this.builtUrl.iframeOrigin);
    }
    this.events.emit("ready", { state: this.lifecycle.state });
    this.events.emit("state_changed", { state: this.lifecycle.state });
    this.readyDeferred.resolve();
    this.logger?.log("Widget ready");
  }

  private readonly handleRuntimeMessage = (event: MessageEvent): void => {
    if (!this.builtUrl || !this.frame) return;
    if (event.origin !== this.builtUrl.iframeOrigin || event.source !== this.frame.iframe.contentWindow) {
      return;
    }
    const result = validateProtocolEnvelope(event.data, { expectedSource: WIDGET_PROTOCOL_SOURCE_IFRAME });
    if (!result.ok) {
      this.events.emit("error", createSDKError("protocol_mismatch", "protocol").toPublicJSON());
      return;
    }
    if (this.recentMessages.hasSeen(result.envelope.messageId)) {
      return;
    }
    this.recentMessages.remember(result.envelope.messageId);
    if (result.envelope.type === "widget_state_changed") {
      this.handleStateChanged(result.envelope);
      return;
    }
    if (result.envelope.type === "resize_request") {
      const payload = result.envelope.payload as { width?: unknown; height?: unknown };
      applyResize(this.frame, payload.width, payload.height);
    }
  };

  private handleStateChanged(envelope: WidgetProtocolEnvelope): void {
    const payload = envelope.payload as { state?: unknown };
    if (payload.state !== "ready_open" && payload.state !== "ready_closed") {
      return;
    }
    if (!this.frame) return;
    const state = payload.state;
    if (this.lifecycle.state !== state) {
      this.lifecycle.transition(state);
    }
    setContainerOpen(this.frame.container, state === "ready_open");
    this.events.emit("state_changed", { state });
    this.events.emit(state === "ready_open" ? "opened" : "closed", { state } as never);
    if (this.pendingCommand?.expectedState === state) {
      clearTimeout(this.pendingCommand.timer);
      const resolve = this.pendingCommand.resolve;
      this.pendingCommand = undefined;
      resolve();
    }
  }

  private async sendStateCommand(type: "open" | "close", expectedState: "ready_open" | "ready_closed"): Promise<void> {
    await this.whenReady();
    if (!this.frame || !this.builtUrl) {
      throw createSDKError("iframe_load_failed", "iframe", { retryable: true });
    }
    if (this.lifecycle.state === expectedState) {
      return;
    }
    if (!this.lifecycle.isReady()) {
      throw createSDKError("invalid_state", "runtime");
    }
    this.clearPendingCommand(createSDKError("command_timeout", "protocol"));
    return new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pendingCommand?.expectedState === expectedState) {
          this.pendingCommand = undefined;
        }
        const error = createSDKError("command_timeout", "protocol", { retryable: true });
        this.events.emit("error", error.toPublicJSON());
        reject(error);
      }, COMMAND_TIMEOUT_MS);
      this.pendingCommand = { expectedState, resolve, reject, timer };
      this.sendFireAndForget(type, {});
    });
  }

  private sendFireAndForget(type: "open" | "close" | "destroy" | "host_visibility_changed", payload: Record<string, unknown>): void {
    if (!this.frame?.iframe.contentWindow || !this.builtUrl) return;
    this.frame.iframe.contentWindow.postMessage(createProtocolEnvelope(type, WIDGET_PROTOCOL_SOURCE_LOADER, payload), this.builtUrl.iframeOrigin);
  }

  private readonly handleViewportResize = (): void => {
    if (!this.frame || !this.lifecycle.isOpen()) return;
    applyResize(this.frame, this.frame.container.offsetWidth, this.frame.container.offsetHeight);
  };

  private readonly handleIframeError = (): void => {
    this.fail(createSDKError("iframe_load_failed", "iframe", { retryable: true }));
  };

  private fail(error: WidgetSDKError): void {
    try {
      if (this.lifecycle.state !== "failed" && this.lifecycle.state !== "destroyed") {
        this.lifecycle.transition("failed");
      }
    } catch {
      this.lifecycle.state = "failed";
    }
    this.readyDeferred.reject(error);
    this.events.emit("error", error.toPublicJSON());
    this.events.emit("state_changed", { state: this.lifecycle.state });
  }

  private clearPendingCommand(error: WidgetSDKError): void {
    if (!this.pendingCommand) return;
    clearTimeout(this.pendingCommand.timer);
    const reject = this.pendingCommand.reject;
    this.pendingCommand = undefined;
    reject(error);
  }

  private async waitForBody(): Promise<void> {
    if (hasDocumentBody(this.documentRef)) return;
    await new Promise<void>((resolve) => {
      this.documentRef.addEventListener("DOMContentLoaded", () => resolve(), { once: true });
    });
  }

  private signatureForInput(input: WidgetSDKConfig): string {
    try {
      const config = assertValidWidgetSDKConfig(input);
      return this.signatureForConfig(config);
    } catch {
      return JSON.stringify(input);
    }
  }

  private signatureForConfig(config: ValidatedWidgetSDKConfig): string {
    return JSON.stringify({
      widgetKey: config.widgetKey,
      environment: config.environment,
      initialOpen: config.initialOpen,
      mountMode: config.mountMode,
      localeHint: config.localeHint ?? null,
      iframeHost: config.hosts.iframeHost,
      sdkHost: config.hosts.sdkHost,
      debug: config.debug,
    });
  }
}
