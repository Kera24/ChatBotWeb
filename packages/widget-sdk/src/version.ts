export const SDK_VERSION = "0.1.0-foundation.0" as const;
export const SDK_MAJOR_VERSION = 1 as const;
export const WIDGET_PROTOCOL_VERSION = 1 as const;
export const PUBLIC_CONFIG_SCHEMA_VERSION = "1.0" as const;
export const PUBLIC_MESSAGE_SCHEMA_VERSION = "1.1" as const;
export const BUILD_MODE = "foundation" as const;

export type SDKVersion = typeof SDK_VERSION;
export type SDKMajorVersion = typeof SDK_MAJOR_VERSION;
export type WidgetProtocolVersion = typeof WIDGET_PROTOCOL_VERSION;