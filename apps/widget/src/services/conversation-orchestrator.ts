import type { PublicWidgetConfigResponse } from "../api/contracts";
import { WidgetApiError, toWidgetApiError, type SafeWidgetApiErrorShape } from "../api/errors";
import { ConversationStore, createConversationId } from "../state/conversation-state";
import type { MessageService } from "./message-service";
import { createIdempotencyKey } from "./message-service";

export type SuggestedQuestion = Readonly<{ id: string; text: string }>;
export type MessageSource = "suggestion" | "composer" | "retry";

export const PUBLIC_MESSAGE_MAX_CHARACTERS = 4000;
export const CHARACTER_COUNT_NOTICE_RATIO = 0.8;

type ValidationResult = Readonly<{
  ok: boolean;
  value: string;
  message: string | null;
  overLimit: boolean;
}>;

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
  source: MessageSource;
}>;

type FailedSend = Readonly<ActiveSend & { error: SafeWidgetApiErrorShape }>;

export class ConversationOrchestrator {
  private activeSend: ActiveSend | null = null;
  private readonly failedSends = new Map<string, FailedSend>();

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
    await this.submitText(suggestion.text, "suggestion");
  }

  async submitCustomMessage(message: string): Promise<void> {
    const validation = validateComposerMessage(message);
    if (!validation.ok) throw new WidgetApiError(validation.overLimit ? "message_rejected" : "message_rejected", "message", { retryable: false, message: validation.message ?? undefined });
    await this.submitText(validation.value, "composer");
  }

  async retry(logicalSendId: string): Promise<void> {
    const failed = this.failedSends.get(logicalSendId);
    if (!failed || this.activeSend) return;
    const retryCreatesFreshOperation = ["invalid_session", "session_expired", "session_limit_reached"].includes(failed.error.code);
    const active: ActiveSend = retryCreatesFreshOperation
      ? Object.freeze({
          logicalSendId: createConversationId("send"),
          userId: createConversationId("user"),
          assistantId: createConversationId("assistant"),
          text: failed.text,
          idempotencyKey: createIdempotencyKey(),
          source: "retry",
        })
      : Object.freeze({ ...failed, source: "retry" });
    this.failedSends.delete(logicalSendId);
    this.activeSend = active;
    this.options.conversationStore.beginLogicalSend(active.text, active.logicalSendId, active.assistantId, active.userId);
    await this.performActiveSend(active);
  }

  private async submitText(text: string, source: MessageSource): Promise<void> {
    if (this.activeSend) return;
    const safeText = source === "suggestion" ? validateSuggestionText(text) : validateComposerMessage(text).value;
    const active: ActiveSend = Object.freeze({
      logicalSendId: createConversationId("send"),
      userId: createConversationId("user"),
      assistantId: createConversationId("assistant"),
      text: safeText,
      idempotencyKey: createIdempotencyKey(),
      source,
    });
    this.activeSend = active;
    this.options.conversationStore.beginLogicalSend(active.text, active.logicalSendId, active.assistantId, active.userId);
    await this.performActiveSend(active);
  }

  private async performActiveSend(active: ActiveSend): Promise<void> {
    try {
      const response = await this.options.messageService.sendMessage(active.text, { source: active.source }, active.idempotencyKey);
      this.options.conversationStore.markUserSent(active.userId);
      this.options.conversationStore.resolveAssistant(active.assistantId, response);
      this.failedSends.delete(active.logicalSendId);
    } catch (error) {
      const safe = toWidgetApiError(error, "message").toSafeShape();
      const recoverable = isExplicitRecoveryAllowed(safe);
      this.options.conversationStore.failLogicalSend(active.userId, active.assistantId, active.logicalSendId, safe, recoverable);
      if (recoverable) this.failedSends.set(active.logicalSendId, Object.freeze({ ...active, error: safe }));
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

export function validateComposerMessage(value: unknown): ValidationResult {
  if (typeof value !== "string") return Object.freeze({ ok: false, value: "", message: "Enter a message before sending.", overLimit: false });
  const normalised = value.replace(/\r\n?/g, "\n").replace(/\u0000/g, "");
  const trimmed = normalised.trim();
  if (!trimmed) return Object.freeze({ ok: false, value: "", message: "Enter a message before sending.", overLimit: false });
  if (/[\u0001-\u0008\u000B\u000C\u000E-\u001F]/.test(trimmed)) {
    return Object.freeze({ ok: false, value: trimmed, message: "Remove unsupported control characters before sending.", overLimit: false });
  }
  if (trimmed.length > PUBLIC_MESSAGE_MAX_CHARACTERS) {
    return Object.freeze({ ok: false, value: trimmed, message: `Keep your message under ${PUBLIC_MESSAGE_MAX_CHARACTERS} characters.`, overLimit: true });
  }
  return Object.freeze({ ok: true, value: trimmed, message: null, overLimit: false });
}

function isExplicitRecoveryAllowed(error: SafeWidgetApiErrorShape): boolean {
  if (error.retryable) return true;
  return ["invalid_session", "session_expired", "network_error", "request_timeout", "temporarily_unavailable"].includes(error.code);
}

function safeSuggestionText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.replace(/\r\n?/g, "\n").trim();
  if (!text || text.length > 180 || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text)) return null;
  return text;
}
