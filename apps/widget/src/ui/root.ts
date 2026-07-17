import { h, render } from "preact";
import type { ConversationSnapshot, ConversationStore } from "../state/conversation-state";
import type { WidgetStateSnapshot, WidgetStateStore } from "../state/widget-state";
import type { ConversationOrchestrator } from "../services/conversation-orchestrator";
import { WidgetApp, type WidgetShellState } from "./components/widget-app";
import { createWidgetDesignTokens, projectTokensToCssVariables, themeInputFromConfig } from "./theme/tokens";

export type WidgetUiController = Readonly<{
  attachStore(store: WidgetStateStore): void;
  attachConversation(store: ConversationStore, orchestrator: ConversationOrchestrator): void;
  setShellState(state: WidgetShellState): void;
  setUnavailable(): void;
  destroy(): void;
}>;

type InternalUiState = {
  shellState: WidgetShellState;
  snapshot: WidgetStateSnapshot | null;
  conversation: ConversationSnapshot | null;
  orchestrator: ConversationOrchestrator | null;
  systemDark: boolean;
};

export function mountWidgetUi(root: HTMLElement, options: Readonly<{ onOpen?: () => void; onClose?: () => void }> = {}): WidgetUiController {
  root.textContent = "";
  root.removeAttribute("role");
  root.removeAttribute("aria-live");
  let state: InternalUiState = { shellState: "loading", snapshot: null, conversation: null, orchestrator: null, systemDark: getSystemDark() };
  let unsubscribeWidget: (() => void) | null = null;
  let unsubscribeConversation: (() => void) | null = null;
  const media = getColourSchemeMedia();
  const handleThemeChange = () => {
    state = { ...state, systemDark: getSystemDark() };
    draw();
  };
  media?.addEventListener?.("change", handleThemeChange);

  function draw(): void {
    root.setAttribute("data-widget-state", state.shellState);
    const tokens = createWidgetDesignTokens(themeInputFromConfig(state.snapshot?.config.data ?? null), state.systemDark);
    root.setAttribute("data-yw-theme", tokens.mode);
    for (const [key, value] of Object.entries(projectTokensToCssVariables(tokens))) {
      root.style.setProperty(key, value);
    }
    render(h(WidgetApp, {
      shellState: state.shellState,
      snapshot: state.snapshot,
      conversation: state.conversation,
      systemDark: state.systemDark,
      onOpen: options.onOpen,
      onClose: options.onClose,
      onSuggestionSelect: (id: string) => { void state.orchestrator?.submitSuggestedQuestion(id); },
      onSubmitMessage: (message: string) => state.orchestrator?.submitCustomMessage(message),
      onRetry: (id: string) => { void state.orchestrator?.retry(id); },
      onRenderError: () => {
        state = { ...state, shellState: "unavailable" };
      },
    }), root);
  }

  draw();

  return Object.freeze({
    attachStore(store: WidgetStateStore) {
      unsubscribeWidget?.();
      unsubscribeWidget = store.subscribe((snapshot) => {
        state = { ...state, snapshot };
        if (snapshot.bootstrapStatus === "unavailable") {
          state = { ...state, shellState: "unavailable" };
        }
        draw();
      });
    },
    attachConversation(store: ConversationStore, orchestrator: ConversationOrchestrator) {
      unsubscribeConversation?.();
      state = { ...state, orchestrator };
      unsubscribeConversation = store.subscribe((conversation) => {
        state = { ...state, conversation };
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
      unsubscribeWidget?.();
      unsubscribeConversation?.();
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
