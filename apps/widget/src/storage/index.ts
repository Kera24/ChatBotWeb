import { BrowserSessionStore } from "./browser-session-store";
import { MemorySessionStore } from "./memory-session-store";
import type { SessionStore } from "./session-store";

export function createSessionStore(windowRef: Window, scope: { widgetKey: string; environment: string }): SessionStore {
  try {
    const browserStore = new BrowserSessionStore(windowRef.sessionStorage, scope);
    if (browserStore.isAvailable()) {
      return browserStore;
    }
  } catch {
    // Fall through to memory storage.
  }
  return new MemorySessionStore(scope);
}