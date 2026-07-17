import { describe, expect, it, vi } from "vitest";
import { ConversationStore } from "../src/state/conversation-state";
import { validMessage } from "./fixtures";

function flush(): Promise<void> {
  return new Promise((resolve) => queueMicrotask(resolve));
}

describe("ConversationStore", () => {
  it("appends user and assistant preparation entries then resolves an answer", async () => {
    const store = new ConversationStore();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    store.beginLogicalSend("What can you do?", "send_1", "assistant_1", "user_1");
    store.markUserSent("user_1");
    store.resolveAssistant("assistant_1", validMessage);
    const snapshot = store.snapshot();
    expect(snapshot.entries).toHaveLength(2);
    expect(snapshot.entries[0]).toMatchObject({ role: "user", status: "sent", content: "What can you do?" });
    expect(snapshot.entries[1]).toMatchObject({ role: "assistant", status: "answered", content: "Safe answer" });
    expect(JSON.stringify(snapshot)).not.toContain("session_token");
    unsubscribe();
    await flush();
    expect(listener).toHaveBeenCalled();
  });

  it("maps fallback and low-confidence answer states", () => {
    const store = new ConversationStore();
    store.beginLogicalSend("Fallback?", "send_1", "assistant_1", "user_1");
    store.resolveAssistant("assistant_1", { ...validMessage, answer_state: "fallback", fallback_used: true, answer: "I could not find this." });
    expect(store.snapshot().entries[1].status).toBe("fallback");
    store.beginLogicalSend("Confidence?", "send_2", "assistant_2", "user_2");
    store.resolveAssistant("assistant_2", { ...validMessage, answer_state: "low_confidence", answer: "This may help." });
    expect(store.snapshot().entries[store.snapshot().entries.length - 1]?.status).toBe("low_confidence");
  });

  it("fails a logical send without leaking idempotency or provider metadata", () => {
    const store = new ConversationStore();
    store.beginLogicalSend("Retry?", "send_1", "assistant_1", "user_1");
    store.failLogicalSend("user_1", "assistant_1", "send_1", { code: "network_error", message: "Network connection failed.", phase: "message", retryable: true });
    const text = JSON.stringify(store.snapshot());
    expect(store.snapshot().entries[0].status).toBe("failed");
    expect(store.snapshot().entries[1].status).toBe("failed");
    expect(text).not.toContain("wid_");
    expect(text).not.toContain("provider");
  });

  it("keeps immutable bounded snapshots", () => {
    const store = new ConversationStore();
    for (let index = 0; index < 105; index += 1) {
      store.beginLogicalSend(`Question ${index}`, `send_${index}`, `assistant_${index}`, `user_${index}`);
    }
    expect(store.snapshot().entries.length).toBeLessThanOrEqual(100);
    expect(Object.isFrozen(store.snapshot())).toBe(true);
    expect(Object.isFrozen(store.snapshot().entries)).toBe(true);
  });
});
