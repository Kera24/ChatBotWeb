export type IframeLifecycleState = "booting" | "waiting_for_initialise" | "ready_closed" | "ready_open" | "failed" | "destroyed";

const transitions: Record<IframeLifecycleState, readonly IframeLifecycleState[]> = {
  booting: ["waiting_for_initialise", "failed", "destroyed"],
  waiting_for_initialise: ["ready_closed", "ready_open", "failed", "destroyed"],
  ready_closed: ["ready_open", "failed", "destroyed"],
  ready_open: ["ready_closed", "failed", "destroyed"],
  failed: ["destroyed"],
  destroyed: [],
};

export class IframeLifecycle {
  public state: IframeLifecycleState = "booting";

  transition(next: IframeLifecycleState): void {
    if (!transitions[this.state].includes(next)) {
      throw new Error(`Invalid iframe lifecycle transition ${this.state} -> ${next}`);
    }
    this.state = next;
  }
}
