import type { WidgetSDKErrorPublic } from "../errors";
import type { WidgetRuntimeState } from "./lifecycle";

export type WidgetSDKEventMap = {
  ready: { state: WidgetRuntimeState };
  opened: { state: "ready_open" };
  closed: { state: "ready_closed" };
  error: WidgetSDKErrorPublic;
  destroyed: { state: "destroyed" };
  state_changed: { state: WidgetRuntimeState };
  degraded: { state: "degraded" };
};

export type WidgetSDKEventName = keyof WidgetSDKEventMap;
export type WidgetSDKEventHandler<TName extends WidgetSDKEventName = WidgetSDKEventName> = (payload: WidgetSDKEventMap[TName]) => void;

export class WidgetEventEmitter {
  private readonly handlers = new Map<WidgetSDKEventName, Set<WidgetSDKEventHandler>>();

  on<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): () => void {
    const set = this.handlers.get(event) ?? new Set<WidgetSDKEventHandler>();
    set.add(handler as WidgetSDKEventHandler);
    this.handlers.set(event, set);
    return () => this.off(event, handler);
  }

  off<TName extends WidgetSDKEventName>(event: TName, handler: WidgetSDKEventHandler<TName>): void {
    this.handlers.get(event)?.delete(handler as WidgetSDKEventHandler);
  }

  emit<TName extends WidgetSDKEventName>(event: TName, payload: WidgetSDKEventMap[TName]): void {
    const set = this.handlers.get(event);
    if (!set) return;
    for (const handler of Array.from(set)) {
      queueMicrotask(() => {
        try {
          (handler as WidgetSDKEventHandler<TName>)(payload);
        } catch {
          // Host callbacks are isolated from SDK runtime state.
        }
      });
    }
  }

  clear(): void {
    this.handlers.clear();
  }
}
