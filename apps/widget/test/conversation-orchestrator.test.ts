import { describe, expect, it, vi } from "vitest";
import { WidgetApiError } from "../src/api/errors";
import { ConversationOrchestrator, deriveSuggestions } from "../src/services/conversation-orchestrator";
import { ConversationStore } from "../src/state/conversation-state";
import { validConfig, validMessage } from "./fixtures";

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("ConversationOrchestrator", () => {
  it("derives bounded unique suggestions from validated config", () => {
    const suggestions = deriveSuggestions({
      ...validConfig,
      behaviour: { ...validConfig.behaviour, max_initial_suggestions: 4, suggested_questions: ["One", "One", "Two", "", "Three"] },
    });
    expect(suggestions.map((item) => item.text)).toEqual(["One", "Two", "Three"]);
  });

  it("submits a validated suggestion through the message service", async () => {
    const store = new ConversationStore();
    const sendMessage = vi.fn().mockResolvedValue(validMessage);
    const orchestrator = new ConversationOrchestrator({
      conversationStore: store,
      messageService: { sendMessage } as never,
      configProvider: () => validConfig,
    });
    await orchestrator.submitSuggestedQuestion("suggestion_1");
    await flush();
    expect(sendMessage).toHaveBeenCalledWith("What can you do?", { source: "suggestion" }, expect.stringMatching(/^wid_/));
    expect(store.snapshot().entries.map((entry) => entry.status)).toEqual(["sent", "answered"]);
  });

  it("prevents concurrent duplicate sends from repeated presses", async () => {
    const store = new ConversationStore();
    let resolveSend!: (value: typeof validMessage) => void;
    const sendMessage = vi.fn().mockReturnValue(new Promise((resolve) => { resolveSend = resolve; }));
    const orchestrator = new ConversationOrchestrator({ conversationStore: store, messageService: { sendMessage } as never, configProvider: () => validConfig });
    const first = orchestrator.submitSuggestedQuestion("suggestion_1");
    const second = orchestrator.submitSuggestedQuestion("suggestion_1");
    resolveSend(validMessage);
    await Promise.all([first, second]);
    expect(sendMessage).toHaveBeenCalledTimes(1);
  });

  it("records retryable failures without exposing sensitive keys", async () => {
    const store = new ConversationStore();
    const sendMessage = vi.fn().mockRejectedValue(new WidgetApiError("network_error", "message", { retryable: true }));
    const orchestrator = new ConversationOrchestrator({ conversationStore: store, messageService: { sendMessage } as never, configProvider: () => validConfig });
    await orchestrator.submitSuggestedQuestion("suggestion_1");
    expect(store.snapshot().entries[store.snapshot().entries.length - 1]?.status).toBe("failed");
    expect(JSON.stringify(store.snapshot())).not.toContain("wid_");
  });
});
