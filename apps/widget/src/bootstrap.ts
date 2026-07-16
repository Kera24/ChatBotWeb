import { resolveParentOriginFromBootstrap } from "./parent-origin";
import { startIframeHandshake } from "./handshake";
import {
  IFRAME_STATE_ATTRIBUTE,
  WIDGET_SHELL_CLOSED_TEXT,
  WIDGET_SHELL_LOADING_TEXT,
  WIDGET_SHELL_OPEN_TEXT,
  WIDGET_SHELL_READY_TEXT,
  WIDGET_SHELL_ROOT_ID,
  WIDGET_SHELL_UNAVAILABLE_TEXT,
} from "./constants";
import "./style.css";

export function renderShell(root: HTMLElement, statusText = WIDGET_SHELL_LOADING_TEXT): void {
  root.setAttribute("role", "status");
  root.setAttribute("aria-live", "polite");
  root.setAttribute(IFRAME_STATE_ATTRIBUTE, "loading");
  root.textContent = statusText;
}

export function setShellReady(root: HTMLElement): void {
  root.setAttribute(IFRAME_STATE_ATTRIBUTE, "ready");
  root.textContent = WIDGET_SHELL_READY_TEXT;
}

export function setShellOpen(root: HTMLElement): void {
  root.setAttribute(IFRAME_STATE_ATTRIBUTE, "open");
  root.textContent = WIDGET_SHELL_OPEN_TEXT;
}

export function setShellClosed(root: HTMLElement): void {
  root.setAttribute(IFRAME_STATE_ATTRIBUTE, "closed");
  root.textContent = WIDGET_SHELL_CLOSED_TEXT;
}

export function setShellFailed(root: HTMLElement): void {
  root.setAttribute(IFRAME_STATE_ATTRIBUTE, "failed");
  root.textContent = WIDGET_SHELL_UNAVAILABLE_TEXT;
}

export function bootstrapWidgetShell(documentRef: Document = document, windowRef: Window = window): void {
  const root = documentRef.getElementById(WIDGET_SHELL_ROOT_ID);
  if (!root) {
    return;
  }
  renderShell(root);
  try {
    const parent = resolveParentOriginFromBootstrap(windowRef.location.href, documentRef.referrer);
    startIframeHandshake({
      parentOrigin: parent.parentOrigin,
      parentWindow: windowRef.parent,
      selfWindow: windowRef,
      onReady: () => setShellReady(root),
      onOpen: () => setShellOpen(root),
      onClose: () => setShellClosed(root),
      onDestroy: () => setShellClosed(root),
      onError: () => setShellFailed(root),
    });
  } catch {
    setShellFailed(root);
  }
}
