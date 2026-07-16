import type { ValidatedWidgetSDKConfig } from "../config";

export type DebugLogger = Readonly<{
  log(message: string, metadata?: Record<string, string | number | boolean>): void;
}>;

export function createDebugLogger(config: ValidatedWidgetSDKConfig): DebugLogger {
  const enabled = config.debug && config.environment === "development";
  return Object.freeze({
    log(message: string, metadata: Record<string, string | number | boolean> = {}) {
      if (!enabled) return;
      const safeMetadata = { ...metadata };
      if ("widgetKey" in safeMetadata) delete safeMetadata.widgetKey;
      console.debug("[YoranixWidget]", message, safeMetadata);
    },
  });
}
