import { RECENT_MESSAGE_ID_LIMIT } from "./constants";

export class RecentMessageTracker {
  private readonly seen = new Set<string>();
  private readonly order: string[] = [];

  constructor(private readonly limit = RECENT_MESSAGE_ID_LIMIT) {}

  hasSeen(messageId: string): boolean {
    return this.seen.has(messageId);
  }

  remember(messageId: string): void {
    if (this.seen.has(messageId)) {
      return;
    }
    this.seen.add(messageId);
    this.order.push(messageId);
    while (this.order.length > this.limit) {
      const removed = this.order.shift();
      if (removed) {
        this.seen.delete(removed);
      }
    }
  }

  clear(): void {
    this.seen.clear();
    this.order.length = 0;
  }
}
