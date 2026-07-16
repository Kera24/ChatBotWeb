import type { WidgetProtocolEnvelope } from "@yoranix/widget-sdk";

export type ParentWindowPort = {
  postMessage(message: unknown, targetOrigin: string): void;
};

export function sendToParent<TPayload>(
  parentWindow: ParentWindowPort,
  envelope: WidgetProtocolEnvelope<TPayload>,
  targetOrigin: string,
): void {
  if (targetOrigin === "*") {
    throw new Error("Wildcard targetOrigin is not allowed for widget protocol messages.");
  }
  parentWindow.postMessage(envelope, targetOrigin);
}
