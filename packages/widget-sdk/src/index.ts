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
export {
  BUILD_MODE,
  PUBLIC_CONFIG_SCHEMA_VERSION,
  PUBLIC_MESSAGE_SCHEMA_VERSION,
  SDK_MAJOR_VERSION,
  SDK_VERSION,
  WIDGET_PROTOCOL_VERSION,
} from "./version";