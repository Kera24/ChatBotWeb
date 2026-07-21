export type WidgetRuntimeState =
  | "uninitialised"
  | "validating"
  | "mounting"
  | "handshaking"
  | "ready_closed"
  | "ready_open"
  | "degraded"
  | "failed"
  | "destroying"
  | "destroyed";

const transitions: Record<WidgetRuntimeState, readonly WidgetRuntimeState[]> = {
  uninitialised: ["validating", "destroyed"],
  validating: ["mounting", "failed", "destroyed"],
  mounting: ["handshaking", "failed", "destroying"],
  handshaking: ["ready_closed", "ready_open", "failed", "destroying"],
  ready_closed: ["ready_open", "degraded", "destroying", "failed"],
  ready_open: ["ready_closed", "degraded", "destroying", "failed"],
  degraded: ["ready_closed", "ready_open", "failed", "destroying"],
  failed: ["destroying", "destroyed"],
  destroying: ["destroyed"],
  destroyed: ["validating"],
};

export class WidgetLifecycle {
  public state: WidgetRuntimeState = "uninitialised";

  transition(next: WidgetRuntimeState): void {
    if (this.state === next) {
      return;
    }
    if (!transitions[this.state].includes(next)) {
      throw new Error(`Invalid widget runtime transition ${this.state} -> ${next}`);
    }
    this.state = next;
  }

  isReady(): boolean {
    return this.state === "ready_closed" || this.state === "ready_open";
  }

  isOpen(): boolean {
    return this.state === "ready_open";
  }
}
