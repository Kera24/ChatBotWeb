import type { PublicCitation, PublicMessageResponse } from "../api/contracts";
import type { SafeWidgetApiErrorShape } from "../api/errors";

export type ConversationEntryRole = "user" | "assistant" | "system";
export type UserMessageStatus = "queued" | "sending" | "sent" | "failed";
export type AssistantMessageStatus = "preparing" | "answered" | "fallback" | "low_confidence" | "failed";
export type SystemNoticeCategory = "informational" | "warning" | "error" | "rate_limit" | "unavailable";
export type ConversationEntryStatus = UserMessageStatus | AssistantMessageStatus | SystemNoticeCategory;

export type ConversationEntry = Readonly<{
  id: string;
  role: ConversationEntryRole;
  createdAt: string;
  status: ConversationEntryStatus;
  content: string;
  answerState?: PublicMessageResponse["answer_state"];
  citations?: readonly PublicCitation[];
  requestId?: string;
  retry?: Readonly<{ retryable: boolean; logicalSendId: string }>;
  error?: SafeWidgetApiErrorShape;
}>;

export type ConversationSnapshot = Readonly<{
  entries: readonly ConversationEntry[];
  activeLogicalSendId: string | null;
  announcement: string | null;
  revision: number;
}>;

export type ConversationListener = (snapshot: ConversationSnapshot) => void;

const MAX_ENTRIES = 100;
const MAX_TOTAL_CONTENT = 60000;
const INITIAL_SNAPSHOT: ConversationSnapshot = Object.freeze({
  entries: Object.freeze([]),
  activeLogicalSendId: null,
  announcement: null,
  revision: 0,
});

export class ConversationStore {
  private snapshotValue: ConversationSnapshot = INITIAL_SNAPSHOT;
  private readonly listeners = new Set<ConversationListener>();

  snapshot(): ConversationSnapshot {
    return this.snapshotValue;
  }

  subscribe(listener: ConversationListener): () => void {
    this.listeners.add(listener);
    listener(this.snapshotValue);
    return () => this.listeners.delete(listener);
  }

  beginLogicalSend(userContent: string, logicalSendId: string, assistantId: string, userId: string = createConversationId("user")): { userId: string; assistantId: string } {
    const now = new Date().toISOString();
    this.setSnapshot({
      entries: this.trimEntries([
        ...this.snapshotValue.entries,
        freezeEntry({ id: userId, role: "user", createdAt: now, status: "sending", content: clampContent(userContent) }),
        freezeEntry({ id: assistantId, role: "assistant", createdAt: now, status: "preparing", content: "Checking the available information" }),
      ]),
      activeLogicalSendId: logicalSendId,
      announcement: "Preparing an answer.",
    });
    return { userId, assistantId };
  }

  markUserSent(userId: string): void {
    this.replaceEntry(userId, (entry) => freezeEntry({ ...entry, status: "sent" }));
  }

  resolveAssistant(assistantId: string, response: PublicMessageResponse): void {
    const status = mapAssistantStatus(response.answer_state, response.fallback_used);
    this.replaceEntry(assistantId, (entry) => freezeEntry({
      ...entry,
      status,
      content: clampContent(response.answer),
      answerState: response.answer_state,
      citations: Object.freeze([...response.citations]),
      requestId: response.request_id,
    }));
    this.setSnapshot({ activeLogicalSendId: null, announcement: status === "fallback" ? "Fallback answer ready." : status === "low_confidence" ? "Low confidence answer ready." : "Answer ready." });
  }

  failLogicalSend(userId: string, assistantId: string, logicalSendId: string, error: SafeWidgetApiErrorShape): void {
    this.replaceEntry(userId, (entry) => freezeEntry({ ...entry, status: "failed", retry: Object.freeze({ retryable: error.retryable, logicalSendId }), error }));
    this.replaceEntry(assistantId, () => freezeEntry({
      id: assistantId,
      role: "assistant",
      createdAt: new Date().toISOString(),
      status: "failed",
      content: messageForError(error),
      retry: Object.freeze({ retryable: error.retryable, logicalSendId }),
      error,
    }));
    this.setSnapshot({ activeLogicalSendId: null, announcement: "Message could not be sent." });
  }

  addSystemNotice(category: SystemNoticeCategory, content: string): void {
    this.setSnapshot({
      entries: this.trimEntries([
        ...this.snapshotValue.entries,
        freezeEntry({ id: createConversationId("notice"), role: "system", createdAt: new Date().toISOString(), status: category, content: clampContent(content) }),
      ]),
      announcement: content,
    });
  }

  clear(): void {
    this.setSnapshot({ entries: Object.freeze([]), activeLogicalSendId: null, announcement: null });
    this.listeners.clear();
  }

  private replaceEntry(id: string, updater: (entry: ConversationEntry) => ConversationEntry): void {
    this.setSnapshot({ entries: Object.freeze(this.snapshotValue.entries.map((entry) => entry.id === id ? updater(entry) : entry)) });
  }

  private setSnapshot(patch: Partial<Omit<ConversationSnapshot, "revision">>): void {
    this.snapshotValue = Object.freeze({
      ...this.snapshotValue,
      ...patch,
      entries: Object.freeze([...(patch.entries ?? this.snapshotValue.entries)]),
      revision: this.snapshotValue.revision + 1,
    });
    for (const listener of [...this.listeners]) {
      queueMicrotask(() => listener(this.snapshotValue));
    }
  }

  private trimEntries(entries: readonly ConversationEntry[]): readonly ConversationEntry[] {
    let next = entries.slice(-MAX_ENTRIES);
    let total = totalContentLength(next);
    while (next.length > 1 && total > MAX_TOTAL_CONTENT) {
      next = next.slice(1);
      total = totalContentLength(next);
    }
    return Object.freeze(next);
  }
}

export function createConversationId(prefix: string): string {
  const cryptoRef = globalThis.crypto;
  if (cryptoRef && typeof cryptoRef.randomUUID === "function") return `${prefix}_${cryptoRef.randomUUID()}`;
  if (cryptoRef && typeof cryptoRef.getRandomValues === "function") {
    const bytes = new Uint8Array(12);
    cryptoRef.getRandomValues(bytes);
    return `${prefix}_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
  }
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

export function mapAssistantStatus(answerState: PublicMessageResponse["answer_state"], fallbackUsed = false): AssistantMessageStatus {
  if (answerState === "low_confidence") return "low_confidence";
  if (answerState === "fallback" || fallbackUsed) return "fallback";
  if (answerState === "temporarily_unavailable") return "failed";
  return "answered";
}

function freezeEntry(entry: ConversationEntry): ConversationEntry {
  return Object.freeze({ ...entry, citations: entry.citations ? Object.freeze([...entry.citations]) : undefined });
}

function clampContent(value: string): string {
  const normalised = value.replace(/\r\n?/g, "\n").replace(/\u0000/g, "").trim();
  return normalised.length > 8000 ? `${normalised.slice(0, 7990)}…` : normalised;
}

function totalContentLength(entries: readonly ConversationEntry[]): number {
  return entries.reduce((total, entry) => total + entry.content.length, 0);
}

function messageForError(error: SafeWidgetApiErrorShape): string {
  if (error.code === "rate_limited") return "Please wait a moment before trying again.";
  if (error.code === "unsafe_request" || error.code === "message_rejected") return "I can’t send that request. Try rephrasing it.";
  if (error.code === "quota_exceeded" || error.code === "session_limit_reached") return "This chat is temporarily limited. Please try again later.";
  if (error.code === "invalid_session" || error.code === "session_expired") return "This chat session is no longer active. Try sending again to start a fresh session.";
  if (error.code === "request_timeout" || error.code === "network_error") return "The connection was interrupted before I could answer.";
  return "I couldn’t get an answer right now. Please try again.";
}
