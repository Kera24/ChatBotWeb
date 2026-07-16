import type { ValidatedWidgetSDKConfig } from "../config";
import type { BuiltIframeUrl } from "../iframe";
import { RECOMMENDED_IFRAME_ATTRIBUTES } from "../iframe";

export const SDK_ROOT_ID = "yoranix-widget-root";
export const SDK_IFRAME_ID = "yoranix-widget-iframe";
export const SDK_STYLE_ID = "yoranix-widget-sdk-style";
export const SDK_CONTAINER_CLASS = "yoranix-widget-container";

export type MountedWidgetFrame = Readonly<{
  container: HTMLElement;
  iframe: HTMLIFrameElement;
}>;

export function hasDocumentBody(documentRef: Document): boolean {
  return Boolean(documentRef.body);
}

export function ensureContainer(documentRef: Document, config: ValidatedWidgetSDKConfig): HTMLElement {
  const existing = documentRef.getElementById(SDK_ROOT_ID);
  if (existing instanceof HTMLElement) {
    return existing;
  }
  const container = documentRef.createElement("div");
  container.id = SDK_ROOT_ID;
  container.className = SDK_CONTAINER_CLASS;
  container.setAttribute("data-yoranix-state", config.initialOpen ? "open" : "closed");
  documentRef.body.appendChild(container);
  return container;
}

export function injectContainerStyles(documentRef: Document, nonce?: string): HTMLStyleElement {
  const existing = documentRef.getElementById(SDK_STYLE_ID);
  if (existing instanceof HTMLStyleElement) {
    return existing;
  }
  const style = documentRef.createElement("style");
  style.id = SDK_STYLE_ID;
  if (nonce) {
    style.setAttribute("nonce", nonce);
  }
  style.textContent = `
#${SDK_ROOT_ID} {
  position: fixed;
  inset-block-end: max(16px, env(safe-area-inset-bottom));
  inset-inline-end: max(16px, env(safe-area-inset-right));
  z-index: 2147483000;
  width: 72px;
  height: 72px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
  pointer-events: none;
}
#${SDK_ROOT_ID}[data-yoranix-state="open"] {
  width: min(380px, calc(100vw - 32px));
  height: min(640px, calc(100vh - 32px));
  pointer-events: auto;
}
#${SDK_ROOT_ID}[data-yoranix-state="closed"] {
  pointer-events: none;
}
#${SDK_IFRAME_ID} {
  border: 0;
  width: 100%;
  height: 100%;
  display: block;
  background: transparent;
  color-scheme: light dark;
  pointer-events: auto;
}
@media (max-width: 480px) {
  #${SDK_ROOT_ID}[data-yoranix-state="open"] {
    inset: 8px;
    width: auto;
    height: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  #${SDK_ROOT_ID}, #${SDK_IFRAME_ID} { transition: none !important; }
}`.trim();
  documentRef.head.appendChild(style);
  return style;
}

export function mountIframe(documentRef: Document, config: ValidatedWidgetSDKConfig, builtUrl: BuiltIframeUrl): MountedWidgetFrame {
  injectContainerStyles(documentRef, config.nonce);
  const container = ensureContainer(documentRef, config);
  const existingIframe = documentRef.getElementById(SDK_IFRAME_ID);
  if (existingIframe instanceof HTMLIFrameElement) {
    existingIframe.remove();
  }
  const iframe = documentRef.createElement("iframe");
  iframe.id = SDK_IFRAME_ID;
  iframe.src = builtUrl.url;
  iframe.title = RECOMMENDED_IFRAME_ATTRIBUTES.title;
  iframe.setAttribute("sandbox", RECOMMENDED_IFRAME_ATTRIBUTES.sandbox);
  iframe.setAttribute("allow", RECOMMENDED_IFRAME_ATTRIBUTES.allow);
  iframe.setAttribute("referrerpolicy", RECOMMENDED_IFRAME_ATTRIBUTES.referrerPolicy);
  iframe.setAttribute("loading", RECOMMENDED_IFRAME_ATTRIBUTES.loading);
  iframe.setAttribute("data-yoranix-widget", "true");
  container.appendChild(iframe);
  return Object.freeze({ container, iframe });
}

export function removeMountedFrame(frame?: MountedWidgetFrame): void {
  frame?.iframe.remove();
  frame?.container.remove();
}

export function setContainerOpen(container: HTMLElement, open: boolean): void {
  container.setAttribute("data-yoranix-state", open ? "open" : "closed");
}

