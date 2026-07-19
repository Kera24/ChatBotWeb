import { validateReleaseConfig } from "./release-config.mjs";

const config = validateReleaseConfig();

process.stdout.write(
  [
    `Widget release configuration valid.`,
    `environment=${config.release_environment}`,
    `channel=${config.release_channel}`,
    `sdk=${config.sdk_version}`,
    `sdkMajor=${config.sdk_major}`,
    `protocol=${config.protocol_major}`,
    `api=${config.api_version}`,
    `widgetOrigin=${config.origins.WIDGET_PUBLIC_ORIGIN}`,
    `apiOrigin=${config.origins.WIDGET_PUBLIC_API_ORIGIN}`,
    `sdkOrigin=${config.origins.WIDGET_SDK_PUBLIC_ORIGIN}`,
  ].join("\n") + "\n",
);
