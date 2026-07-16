import type {
  ALL_WIDGET_MESSAGE_TYPES,
  LOADER_TO_IFRAME_MESSAGE_TYPES,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
} from "./constants";
import type { WidgetEnvironment } from "../environment";
import type { WidgetMountMode } from "../config";

export type WidgetProtocolSource =
  | typeof WIDGET_PROTOCOL_SOURCE_LOADER
  | typeof WIDGET_PROTOCOL_SOURCE_IFRAME;

export type WidgetProtocolMessageType = (typeof ALL_WIDGET_MESSAGE_TYPES)[number];
export type LoaderToIframeMessageType = (typeof LOADER_TO_IFRAME_MESSAGE_TYPES)[number];

export type WidgetProtocolEnvelope<TPayload = unknown> = Readonly<{
  protocol: string;
  version: number;
  messageId: string;
  type: WidgetProtocolMessageType;
  source: WidgetProtocolSource;
  payload: TPayload;
  sentAt: string;
}>;

export type ProtocolErrorCode =
  | "invalid_envelope"
  | "unsupported_protocol"
  | "origin_mismatch"
  | "source_mismatch"
  | "invalid_parent_origin"
  | "handshake_timeout"
  | "duplicate_initialise"
  | "invalid_state"
  | "iframe_unavailable"
  | "destroyed"
  | "safe_internal_error";

export type SafeProtocolError = Readonly<{
  code: ProtocolErrorCode;
  message: string;
  retryable: boolean;
  phase: "bootstrap" | "handshake" | "protocol" | "runtime";
}>;

export type InitialisePayload = Readonly<{
  widgetKey: string;
  parentOrigin: string;
  sdkVersion: string;
  protocolVersion: number;
  environment: WidgetEnvironment;
  initialOpen: boolean;
  mountMode: WidgetMountMode;
  localeHint?: string;
  debug: boolean;
}>;

export type IframeReadyPayload = Readonly<{
  protocolVersion: number;
}>;

export type WidgetReadyPayload = Readonly<{
  state: "ready_closed" | "ready_open";
}>;

export type HandshakeErrorPayload = SafeProtocolError;

export type ResizeRequestPayload = Readonly<{
  width: number;
  height: number;
}>;

export type WidgetStateChangedPayload = Readonly<{
  state: "ready_closed" | "ready_open" | "failed" | "destroyed";
}>;

export type HostVisibilityChangedPayload = Readonly<{
  visible: boolean;
}>;
