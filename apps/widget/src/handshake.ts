import {
  createProtocolEnvelope,
  createSafeProtocolError,
  RecentMessageTracker,
  validateInitialisePayload,
  validateProtocolEnvelope,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
  WIDGET_PROTOCOL_VERSION,
  type InitialisePayload,
  type SafeProtocolError,
} from "@yoranix/widget-sdk";
import { IframeShellError } from "./errors";
import { IframeLifecycle } from "./lifecycle";
import { sendToParent, type ParentWindowPort } from "./protocol";

export type IframeHandshakeOptions = {
  parentOrigin: string;
  parentWindow: ParentWindowPort;
  selfWindow: Window;
  onInitialise?: (payload: InitialisePayload) => void | Promise<void>;
  onReady?: (payload: InitialisePayload) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onDestroy?: () => void;
  onVisibilityChanged?: (visible: boolean) => void;
  onError?: (error: SafeProtocolError) => void;
};

export class IframeHandshakeController {
  public readonly lifecycle = new IframeLifecycle();
  private readonly recentMessages = new RecentMessageTracker();
  private initialised = false;

  constructor(private readonly options: IframeHandshakeOptions) {}

  start(): void {
    this.lifecycle.transition("waiting_for_initialise");
    this.options.selfWindow.addEventListener("message", this.handleMessage);
    this.post("iframe_ready", { protocolVersion: WIDGET_PROTOCOL_VERSION });
  }

  destroy(): void {
    this.options.selfWindow.removeEventListener("message", this.handleMessage);
    if (this.lifecycle.state !== "destroyed") {
      this.lifecycle.transition("destroyed");
    }
    this.options.onDestroy?.();
  }

  private readonly handleMessage = (event: MessageEvent): void => {
    if (event.source !== this.options.parentWindow) {
      this.reportError(createSafeProtocolError("source_mismatch", "handshake"));
      return;
    }
    if (event.origin !== this.options.parentOrigin) {
      this.reportError(createSafeProtocolError("origin_mismatch", "handshake"));
      return;
    }
    const envelopeResult = validateProtocolEnvelope(event.data, { expectedSource: WIDGET_PROTOCOL_SOURCE_LOADER });
    if (!envelopeResult.ok) {
      this.reportError(envelopeResult.error);
      return;
    }
    const envelope = envelopeResult.envelope;
    if (this.recentMessages.hasSeen(envelope.messageId)) {
      return;
    }
    this.recentMessages.remember(envelope.messageId);
    if (envelope.type === "initialise") {
      void this.handleInitialise(envelope.payload);
      return;
    }
    if (envelope.type === "open") {
      this.handleOpen();
      return;
    }
    if (envelope.type === "close") {
      this.handleClose();
      return;
    }
    if (envelope.type === "destroy") {
      this.destroy();
      return;
    }
    if (envelope.type === "host_visibility_changed") {
      const payload = envelope.payload as { visible?: unknown };
      if (typeof payload.visible === "boolean") {
        this.options.onVisibilityChanged?.(payload.visible);
      }
    }
  };

  private async handleInitialise(payload: unknown): Promise<void> {
    if (this.initialised) {
      this.reportError(createSafeProtocolError("duplicate_initialise", "handshake"));
      return;
    }
    if (!validateInitialisePayload(payload)) {
      this.reportError(createSafeProtocolError("invalid_envelope", "handshake"));
      return;
    }
    if (payload.parentOrigin !== this.options.parentOrigin) {
      this.reportError(createSafeProtocolError("origin_mismatch", "handshake"));
      return;
    }
    this.initialised = true;
    this.lifecycle.transition(payload.initialOpen ? "ready_open" : "ready_closed");
    try {
      await this.options.onInitialise?.(payload);
    } catch {
      this.reportError(createSafeProtocolError("safe_internal_error", "handshake"));
      return;
    }
    if (this.lifecycle.state === "failed" || this.lifecycle.state === "destroyed") {
      return;
    }
    this.post("widget_ready", { state: this.lifecycle.state });
    this.postResizeForState();
    this.options.onReady?.(payload);
    if (payload.initialOpen) {
      this.options.onOpen?.();
    }
  }

  private handleOpen(): void {
    if (this.lifecycle.state === "ready_closed") {
      this.lifecycle.transition("ready_open");
      this.post("widget_state_changed", { state: this.lifecycle.state });
      this.postResizeForState();
      this.options.onOpen?.();
    }
  }

  private handleClose(): void {
    if (this.lifecycle.state === "ready_open") {
      this.lifecycle.transition("ready_closed");
      this.post("widget_state_changed", { state: this.lifecycle.state });
      this.postResizeForState();
      this.options.onClose?.();
    }
  }

  private post<TPayload>(type: "iframe_ready" | "widget_ready" | "widget_state_changed" | "resize_request", payload: TPayload): void {
    sendToParent(this.options.parentWindow, createProtocolEnvelope(type, WIDGET_PROTOCOL_SOURCE_IFRAME, payload), this.options.parentOrigin);
  }

  private postResizeForState(): void {
    if (this.lifecycle.state === "ready_open") {
      this.post("resize_request", { width: 380, height: 640 });
      return;
    }
    if (this.lifecycle.state === "ready_closed") {
      this.post("resize_request", { width: 72, height: 72 });
    }
  }

  private reportError(error: SafeProtocolError): void {
    if (this.lifecycle.state !== "failed" && this.lifecycle.state !== "destroyed") {
      this.lifecycle.transition("failed");
    }
    sendToParent(
      this.options.parentWindow,
      createProtocolEnvelope("handshake_error", WIDGET_PROTOCOL_SOURCE_IFRAME, error),
      this.options.parentOrigin,
    );
    this.options.onError?.(error);
  }
}

export function startIframeHandshake(options: IframeHandshakeOptions): IframeHandshakeController {
  const controller = new IframeHandshakeController(options);
  try {
    controller.start();
  } catch (error) {
    const safeError = error instanceof IframeShellError ? error.safeError : createSafeProtocolError("safe_internal_error", "handshake");
    options.onError?.(safeError);
    throw error;
  }
  return controller;
}