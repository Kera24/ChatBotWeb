import { h, render } from "preact";
import type { WidgetStateSnapshot, WidgetStateStore } from "../state/widget-state";
import { WidgetApp, type WidgetShellState } from "./components/widget-app";
import { createWidgetDesignTokens, projectTokensToCssVariables, themeInputFromConfig } from "./theme/tokens";

export type WidgetUiController = Readonly<{
  attachStore(store: WidgetStateStore): void;
  setShellState(state: WidgetShellState): void;
  setUnavailable(): void;
  destroy(): void;
}>;

type InternalUiState = {
  shellState: WidgetShellState;
  snapshot: WidgetStateSnapshot | null;
  systemDark: boolean;
};

export function mountWidgetUi(root: HTMLElement, options: Readonly<{ onOpen?: () => void; onClose?: () => void }> = {}): WidgetUiController {
  root.textContent = "";
  root.removeAttribute("role");
  root.removeAttribute("aria-live");
  let state: InternalUiState = { shellState: "loading", snapshot: null, systemDark: getSystemDark() };
  let unsubscribe: (() => void) | null = null;
  const media = getColourSchemeMedia();
  const handleThemeChange = () => {
    state = { ...state, systemDark: getSystemDark() };
    draw();
  };
  media?.addEventListener?.("change", handleThemeChange);

  function draw(): void {
    root.setAttribute("data-widget-state", state.shellState);
    root.setAttribute("data-yw-theme", state.systemDark ? "dark" : "light");
    const tokens = createWidgetDesignTokens(themeInputFromConfig(state.snapshot?.config.data ?? null), state.systemDark);
    for (const [key, value] of Object.entries(projectTokensToCssVariables(tokens))) {
      root.style.setProperty(key, value);
    }
    render(h(WidgetApp, {
      shellState: state.shellState,
      snapshot: state.snapshot,
      systemDark: state.systemDark,
      onOpen: options.onOpen,
      onClose: options.onClose,
      onRenderError: () => {
        state = { ...state, shellState: "unavailable" };
      },
    }), root);
  }

  draw();

  return Object.freeze({
    attachStore(store: WidgetStateStore) {
      unsubscribe?.();
      unsubscribe = store.subscribe((snapshot) => {
        state = { ...state, snapshot };
        if (snapshot.bootstrapStatus === "unavailable") {
          state = { ...state, shellState: "unavailable" };
        }
        draw();
      });
    },
    setShellState(next: WidgetShellState) {
      state = { ...state, shellState: next };
      draw();
    },
    setUnavailable() {
      state = { ...state, shellState: "unavailable" };
      draw();
    },
    destroy() {
      unsubscribe?.();
      media?.removeEventListener?.("change", handleThemeChange);
      state = { ...state, shellState: "destroyed" };
      render(null, root);
      root.setAttribute("data-widget-state", "destroyed");
    },
  });
}

function getColourSchemeMedia(): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;
}

function getSystemDark(): boolean {
  return getColourSchemeMedia()?.matches ?? false;
}

