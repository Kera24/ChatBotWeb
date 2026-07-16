import { createProtocolEnvelope, WIDGET_PROTOCOL_SOURCE_LOADER } from "../protocol";

export type VisibilityNotifier = Readonly<{
  detach(): void;
}>;

export function attachVisibilityNotifier(
  documentRef: Document,
  targetWindow: Window,
  targetOrigin: string,
): VisibilityNotifier {
  const notify = () => {
    targetWindow.postMessage(
      createProtocolEnvelope("host_visibility_changed", WIDGET_PROTOCOL_SOURCE_LOADER, { visible: !documentRef.hidden }),
      targetOrigin,
    );
  };
  documentRef.addEventListener("visibilitychange", notify);
  window.addEventListener("pagehide", notify);
  window.addEventListener("pageshow", notify);
  return Object.freeze({
    detach() {
      documentRef.removeEventListener("visibilitychange", notify);
      window.removeEventListener("pagehide", notify);
      window.removeEventListener("pageshow", notify);
    },
  });
}
