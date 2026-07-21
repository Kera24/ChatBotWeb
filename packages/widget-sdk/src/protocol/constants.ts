export const WIDGET_PROTOCOL_NAME = "yoranix.widget" as const;
export const WIDGET_PROTOCOL_VERSION = 1 as const;
export const SUPPORTED_WIDGET_PROTOCOL_VERSIONS = [1] as const;

export const WIDGET_PROTOCOL_SOURCE_LOADER = "yoranix-loader" as const;
export const WIDGET_PROTOCOL_SOURCE_IFRAME = "yoranix-iframe" as const;

export const IFRAME_TO_LOADER_MESSAGE_TYPES = [
  "iframe_ready",
  "widget_ready",
  "handshake_error",
  "resize_request",
  "widget_state_changed",
] as const;

export const LOADER_TO_IFRAME_MESSAGE_TYPES = [
  "initialise",
  "open",
  "close",
  "destroy",
  "host_visibility_changed",
] as const;

export const ALL_WIDGET_MESSAGE_TYPES = [
  ...IFRAME_TO_LOADER_MESSAGE_TYPES,
  ...LOADER_TO_IFRAME_MESSAGE_TYPES,
] as const;

export const MAX_PROTOCOL_MESSAGE_ID_LENGTH = 80 as const;
export const MAX_PROTOCOL_ENVELOPE_BYTES = 8192 as const;
export const MAX_PROTOCOL_PAYLOAD_KEYS = 16 as const;
export const MAX_PROTOCOL_STRING_LENGTH = 512 as const;
export const RECENT_MESSAGE_ID_LIMIT = 64 as const;

export const IFRAME_READY_TIMEOUT_MS = 10_000 as const;
export const INITIALISE_ACK_TIMEOUT_MS = 10_000 as const;
export const HANDSHAKE_RETRY_LIMIT = 1 as const;
