export type {
  ConfigValidationResult,
  ValidatedWidgetSDKConfig,
  WidgetMountMode,
  WidgetSDKConfig,
} from "./config";
export { assertValidWidgetSDKConfig, validateWidgetSDKConfig } from "./config";
export type { ResolvedWidgetEnvironment, WidgetEnvironment } from "./environment";
export { isWidgetEnvironment, normaliseHostUrl, resolveWidgetEnvironment } from "./environment";
export type { WidgetSDKErrorCode, WidgetSDKErrorPhase, WidgetSDKErrorPublic } from "./errors";
export { createSDKError, WidgetSDKError } from "./errors";
export { buildInitialisePayload, SDKHandshakeController } from "./handshake";
export type { SDKHandshakeControllerOptions, SDKHandshakeState } from "./handshake";
export { buildWidgetIframeUrl, normaliseOrigin, RECOMMENDED_IFRAME_ATTRIBUTES } from "./iframe";
export type { BuiltIframeUrl } from "./iframe";
export * from "./protocol";
export * from "./runtime";
export {
  BUILD_MODE,
  PUBLIC_CONFIG_SCHEMA_VERSION,
  PUBLIC_MESSAGE_SCHEMA_VERSION,
  SDK_MAJOR_VERSION,
  SDK_VERSION,
  WIDGET_PROTOCOL_VERSION,
} from "./version";

import { autoInstallGlobalAPI } from "./runtime/public-api";

autoInstallGlobalAPI();
