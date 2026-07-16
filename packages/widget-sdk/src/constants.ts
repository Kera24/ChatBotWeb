export const DEFAULT_SDK_HOSTS = {
  development: "http://localhost:4300",
  staging: "https://widget-staging.yoranix.com",
  production: "https://widget.yoranix.com",
} as const;

export const DEFAULT_IFRAME_HOSTS = {
  development: "http://localhost:4301",
  staging: "https://widget-staging.yoranix.com",
  production: "https://widget.yoranix.com",
} as const;

export const DEFAULT_API_HOSTS = {
  development: "http://localhost:8000",
  staging: "https://api-staging.yoranix.com",
  production: "https://api.yoranix.com",
} as const;

export const SUPPORTED_ENVIRONMENTS = ["development", "staging", "production"] as const;
export const SUPPORTED_MOUNT_MODES = ["floating", "inline"] as const;
export const FUTURE_GLOBAL_NAMESPACE = "YoranixWidget" as const;
export const IIFE_FOUNDATION_GLOBAL = "YoranixWidgetSDK" as const;
export const MAX_LOCALE_HINT_LENGTH = 35 as const;
export const MAX_NONCE_LENGTH = 256 as const;