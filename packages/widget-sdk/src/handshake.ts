import { createSDKError, WidgetSDKError } from "./errors";
import {
  createProtocolEnvelope,
  IFRAME_READY_TIMEOUT_MS,
  INITIALISE_ACK_TIMEOUT_MS,
  RecentMessageTracker,
  validateProtocolEnvelope,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
  WIDGET_PROTOCOL_VERSION,
  type InitialisePayload,
  type SafeProtocolError,
} from "./protocol";

export type SDKHandshakeState = "idle" | "waiting_for_iframe_ready" | "initialising" | "ready" | "failed" | "destroyed";

export type HandshakeTimers = {
  setTimeout(callback: () => void, delayMs: number): ReturnType<typeof setTimeout>;
  clearTimeout(timerId: ReturnType<typeof setTimeout>): void;
};

export type SDKHandshakeControllerOptions = {
  iframeWindow: Window;
  iframeOrigin: string;
  initialisePayload: InitialisePayload;
  parentWindow?: Window;
  timers?: HandshakeTimers;
  readyTimeoutMs?: number;
  ackTimeoutMs?: number;
  onReady?: () => void;
  onError?: (error: WidgetSDKError | SafeProtocolError) => void;
};

export class SDKHandshakeController {
  public state: SDKHandshakeState = "idle";
  private readonly recentMessages = new RecentMessageTracker();
  private readonly parentWindow: Window;
  private readonly timers: HandshakeTimers;
  private readyTimer?: ReturnType<typeof setTimeout>;
  private ackTimer?: ReturnType<typeof setTimeout>;
  private retryUsed = false;

  constructor(private readonly options: SDKHandshakeControllerOptions) {
    this.parentWindow = options.parentWindow ?? window;
    this.timers = options.timers ?? {
      setTimeout: (callback, delayMs) => setTimeout(callback, delayMs),
      clearTimeout: (timerId) => clearTimeout(timerId),
    };
  }

  start(): void {
    if (this.state === "destroyed") {
      this.fail(createSDKError("destroyed", "bootstrap"));
      return;
    }
    if (this.state !== "idle") {
      this.fail(createSDKError("duplicate_initialisation", "bootstrap"));
      return;
    }
    this.state = "waiting_for_iframe_ready";
    this.parentWindow.addEventListener("message", this.handleMessage);
    this.readyTimer = this.timers.setTimeout(() => this.handleReadyTimeout(), this.options.readyTimeoutMs ?? IFRAME_READY_TIMEOUT_MS);
  }

  destroy(): void {
    this.clearTimers();
    this.parentWindow.removeEventListener("message", this.handleMessage);
    this.recentMessages.clear();
    this.state = "destroyed";
  }

  private readonly handleMessage = (event: MessageEvent): void => {
    if (this.state === "destroyed") {
      return;
    }
    if (event.origin !== this.options.iframeOrigin) {
      this.fail(createSDKError("protocol_mismatch", "protocol", { safeMetadata: { reason: "origin_mismatch" } }));
      return;
    }
    if (event.source !== this.options.iframeWindow) {
      this.fail(createSDKError("protocol_mismatch", "protocol", { safeMetadata: { reason: "source_mismatch" } }));
      return;
    }
    const result = validateProtocolEnvelope(event.data, { expectedSource: WIDGET_PROTOCOL_SOURCE_IFRAME });
    if (!result.ok) {
      this.fail(createSDKError("protocol_mismatch", "protocol"));
      return;
    }
    if (this.recentMessages.hasSeen(result.envelope.messageId)) {
      return;
    }
    this.recentMessages.remember(result.envelope.messageId);
    if (result.envelope.type === "iframe_ready") {
      this.onIframeReady();
      return;
    }
    if (result.envelope.type === "widget_ready") {
      this.onWidgetReady();
      return;
    }
    if (result.envelope.type === "handshake_error") {
      this.fail(createSDKError("protocol_mismatch", "protocol"));
    }
  };

  private onIframeReady(): void {
    if (this.state !== "waiting_for_iframe_ready") {
      return;
    }
    if (this.readyTimer) {
      this.timers.clearTimeout(this.readyTimer);
    }
    this.state = "initialising";
    this.postInitialise();
    this.ackTimer = this.timers.setTimeout(() => this.handleAckTimeout(), this.options.ackTimeoutMs ?? INITIALISE_ACK_TIMEOUT_MS);
  }

  private postInitialise(): void {
    const envelope = createProtocolEnvelope("initialise", WIDGET_PROTOCOL_SOURCE_LOADER, this.options.initialisePayload);
    this.options.iframeWindow.postMessage(envelope, this.options.iframeOrigin);
  }

  private onWidgetReady(): void {
    if (this.state !== "initialising") {
      return;
    }
    this.clearTimers();
    this.parentWindow.removeEventListener("message", this.handleMessage);
    this.state = "ready";
    this.options.onReady?.();
  }

  private handleReadyTimeout(): void {
    if (this.state !== "waiting_for_iframe_ready") {
      return;
    }
    if (!this.retryUsed) {
      this.retryUsed = true;
      this.readyTimer = this.timers.setTimeout(() => this.handleReadyTimeout(), this.options.readyTimeoutMs ?? IFRAME_READY_TIMEOUT_MS);
      return;
    }
    this.fail(createSDKError("iframe_load_failed", "bootstrap", { retryable: true }));
  }

  private handleAckTimeout(): void {
    if (this.state !== "initialising") {
      return;
    }
    this.fail(createSDKError("protocol_mismatch", "protocol", { retryable: true }));
  }

  private fail(error: WidgetSDKError): void {
    this.clearTimers();
    this.parentWindow.removeEventListener("message", this.handleMessage);
    this.state = this.state === "destroyed" ? "destroyed" : "failed";
    this.options.onError?.(error);
  }

  private clearTimers(): void {
    if (this.readyTimer) {
      this.timers.clearTimeout(this.readyTimer);
      this.readyTimer = undefined;
    }
    if (this.ackTimer) {
      this.timers.clearTimeout(this.ackTimer);
      this.ackTimer = undefined;
    }
  }
}

export function buildInitialisePayload(input: Omit<InitialisePayload, "protocolVersion">): InitialisePayload {
  return Object.freeze({ ...input, protocolVersion: WIDGET_PROTOCOL_VERSION });
}
