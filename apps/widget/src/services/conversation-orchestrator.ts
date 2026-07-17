import type { PublicWidgetConfigResponse } from "../api/contracts";
import { WidgetApiError, toWidgetApiError } from "../api/errors";
import { ConversationStore, createConversationId } from "../state/conversation-state";
import type { MessageService } from "./message-service";
import { createIdempotencyKey } from "./message-service";

export type SuggestedQuestion = Readonly<{ id: string; text: string }>;

export type ConversationOrchestratorOptions = Readonly<{
  conversationStore: ConversationStore;
  messageService: MessageService;
  configProvider: () => PublicWidgetConfigResponse | null;
}>;

type ActiveSend = Readonly<{
  logicalSendId: string;
  userId: string;
  assistantId: string;
  text: string;
  idempotencyKey: string;
}>;

export class ConversationOrchestrator {
  private activeSend: ActiveSend | null = null;
  private readonly failedSends = new Map<string, ActiveSend>();

  constructor(private readonly options: ConversationOrchestratorOptions) {}

  suggestions(): readonly SuggestedQuestion[] {
    return deriveSuggestions(this.options.configProvider());
  }

  isBusy(): boolean {
    return this.activeSend !== null;
  }

  async submitSuggestedQuestion(questionId: string): Promise<void> {
    const suggestion = this.suggestions().find((item) => item.id === questionId);
    if (!suggestion) throw new WidgetApiError("message_rejected", "message", { retryable: false });
    await this.submitText(suggestion.text);
  }

  async retry(logicalSendId: string): Promise<void> {
    const failed = this.failedSends.get(logicalSendId);
    if (!failed || this.activeSend) return;
    this.activeSend = failed;
    this.options.conversationStore.beginLogicalSend(failed.text, failed.logicalSendId, failed.assistantId, failed.userId);
    await this.performActiveSend(failed);
  }

  private async submitText(text: string): Promise<void> {
    if (this.activeSend) return;
    const safeText = validateSuggestionText(text);
    const active: ActiveSend = Object.freeze({
      logicalSendId: createConversationId("send"),
      userId: createConversationId("user"),
      assistantId: createConversationId("assistant"),
      text: safeText,
      idempotencyKey: createIdempotencyKey(),
    });
    this.activeSend = active;
    this.options.conversationStore.beginLogicalSend(active.text, active.logicalSendId, active.assistantId, active.userId);
    await this.performActiveSend(active);
  }

  private async performActiveSend(active: ActiveSend): Promise<void> {
    try {
      const response = await this.options.messageService.sendMessage(active.text, { source: "suggestion" }, active.idempotencyKey);
      this.options.conversationStore.markUserSent(active.userId);
      this.options.conversationStore.resolveAssistant(active.assistantId, response);
      this.failedSends.delete(active.logicalSendId);
    } catch (error) {
      const safe = toWidgetApiError(error, "message").toSafeShape();
      this.options.conversationStore.failLogicalSend(active.userId, active.assistantId, active.logicalSendId, safe);
      if (safe.retryable) this.failedSends.set(active.logicalSendId, active);
    } finally {
      if (this.activeSend?.logicalSendId === active.logicalSendId) this.activeSend = null;
    }
  }
}

export function deriveSuggestions(config: PublicWidgetConfigResponse | null): readonly SuggestedQuestion[] {
  if (!config || !config.capabilities.can_send_messages || !config.behaviour.messages_enabled) return Object.freeze([]);
  const max = Math.max(0, Math.min(config.behaviour.max_initial_suggestions || 0, 4));
  const seen = new Set<string>();
  const output: SuggestedQuestion[] = [];
  for (const raw of config.behaviour.suggested_questions) {
    const text = safeSuggestionText(raw);
    if (!text) continue;
    const key = text.toLocaleLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(Object.freeze({ id: `suggestion_${output.length + 1}`, text }));
    if (output.length >= max) break;
  }
  return Object.freeze(output);
}

export function validateSuggestionText(value: string): string {
  const text = safeSuggestionText(value);
  if (!text) throw new WidgetApiError("message_rejected", "message", { retryable: false });
  return text;
}

function safeSuggestionText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.replace(/\r\n?/g, "\n").trim();
  if (!text || text.length > 180 || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text)) return null;
  return text;
}
