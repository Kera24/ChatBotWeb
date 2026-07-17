import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import type { ComponentChildren } from "preact";
import type { PublicWidgetConfigResponse } from "../../api/contracts";
import type { ConversationEntry, ConversationSnapshot } from "../../state/conversation-state";
import { deriveSuggestions, type SuggestedQuestion } from "../../services/conversation-orchestrator";
import type { WidgetStateSnapshot } from "../../state/widget-state";
import { SafeRasterAsset } from "../assets/safe-raster-asset";
import { WidgetRenderErrorBoundary } from "./error-boundary";

export type WidgetShellState = "loading" | "closed" | "open" | "unavailable" | "destroyed";

export type WidgetAppProps = Readonly<{
  shellState: WidgetShellState;
  snapshot: WidgetStateSnapshot | null;
  conversation?: ConversationSnapshot | null;
  systemDark: boolean;
  onOpen?: () => void;
  onClose?: () => void;
  onSuggestionSelect?: (id: string) => void;
  onRetry?: (logicalSendId: string) => void;
  onRenderError?: () => void;
}>;

const FALLBACK_BOT_NAME = "Yoranix assistant";
const FALLBACK_LAUNCHER_LABEL = "Open chat";
const FALLBACK_WELCOME = "Ask a question and I’ll check the available information.";

export function WidgetApp(props: WidgetAppProps) {
  const config = props.snapshot?.config.data ?? null;
  const botName = safeText(config?.widget.bot_name, FALLBACK_BOT_NAME, 80);
  const launcherLabel = safeText(config?.widget.launcher_label, FALLBACK_LAUNCHER_LABEL, 80);
  const position = normalisePosition(config?.widget.position);
  const isOpen = props.shellState === "open";
  const isUnavailable = props.shellState === "unavailable" || props.snapshot?.bootstrapStatus === "unavailable";

  return (
    <WidgetRenderErrorBoundary onError={props.onRenderError}>
      <WidgetRoot shellState={props.shellState} position={position}>
        <WidgetLauncher label={launcherLabel} isOpen={isOpen} unavailable={isUnavailable} onToggle={isOpen ? props.onClose : props.onOpen} />
        {isOpen ? <WidgetPanel {...props} botName={botName} config={config} unavailable={isUnavailable} /> : null}
      </WidgetRoot>
    </WidgetRenderErrorBoundary>
  );
}

function WidgetRoot({ shellState, position, children }: Readonly<{ shellState: WidgetShellState; position: "left" | "right"; children: ComponentChildren }>) {
  return <div className={`yw-root yw-root--${position}`} data-widget-state={shellState}>{children}</div>;
}

function WidgetLauncher(props: Readonly<{ label: string; isOpen: boolean; unavailable: boolean; onToggle?: () => void }>) {
  return (
    <button
      type="button"
      className="yw-launcher"
      aria-label={props.isOpen ? "Close chat" : props.label}
      aria-expanded={props.isOpen}
      data-open={props.isOpen ? "true" : "false"}
      data-unavailable={props.unavailable ? "true" : "false"}
      onClick={props.onToggle}
    >
      <span className="yw-launcher__mark" aria-hidden="true">{props.isOpen ? "×" : <LauncherGlyph />}</span>
      <span className="yw-launcher__label">{props.isOpen ? "Close" : props.label}</span>
    </button>
  );
}

function WidgetPanel(props: WidgetAppProps & Readonly<{ botName: string; config: PublicWidgetConfigResponse | null; unavailable: boolean }>) {
  return (
    <section className="yw-panel" role="dialog" aria-modal="false" aria-labelledby="yw-panel-title">
      <WidgetHeader botName={props.botName} config={props.config} onClose={props.onClose} />
      <WidgetStatusRegion unavailable={props.unavailable} ready={Boolean(props.config)} />
      <WidgetViewport
        unavailable={props.unavailable}
        ready={Boolean(props.config)}
        botName={props.botName}
        config={props.config}
        conversation={props.conversation}
        onSuggestionSelect={props.onSuggestionSelect}
        onRetry={props.onRetry}
      />
      <WidgetFooterShell />
    </section>
  );
}

function WidgetHeader(props: Readonly<{ botName: string; config: PublicWidgetConfigResponse | null; onClose?: () => void }>) {
  return (
    <header className="yw-header">
      <div className="yw-header__avatar" aria-hidden="true">
        <SafeRasterAsset src={props.config?.widget.avatar_url ?? props.config?.widget.logo_url ?? null} alt="" className="yw-header__avatar-img" />
      </div>
      <div className="yw-header__identity">
        <h1 id="yw-panel-title" className="yw-header__title">{props.botName}</h1>
        <p className="yw-header__status">AI assistant</p>
      </div>
      <button type="button" className="yw-header__close" aria-label="Close chat" onClick={props.onClose}>×</button>
    </header>
  );
}

function WidgetStatusRegion(props: Readonly<{ unavailable: boolean; ready: boolean }>) {
  if (props.unavailable) return <div className="yw-status yw-status--alert" role="alert">The assistant is temporarily unavailable.</div>;
  if (!props.ready) return <div className="yw-status" role="status" aria-live="polite">Loading widget...</div>;
  return <div className="yw-status yw-status--ready" role="status" aria-live="polite">Ready for questions</div>;
}

function WidgetViewport(props: Readonly<{
  unavailable: boolean;
  ready: boolean;
  botName: string;
  config: PublicWidgetConfigResponse | null;
  conversation?: ConversationSnapshot | null;
  onSuggestionSelect?: (id: string) => void;
  onRetry?: (logicalSendId: string) => void;
}>) {
  if (props.unavailable) {
    return <main className="yw-viewport" role="region" aria-label="Chat conversation"><WidgetUnavailableState /></main>;
  }
  if (!props.ready || !props.config) {
    return <main className="yw-viewport" role="region" aria-label="Chat conversation"><WidgetLoadingState /></main>;
  }
  return <ConversationViewport {...props} config={props.config} conversation={props.conversation ?? EMPTY_CONVERSATION} />;
}

const EMPTY_CONVERSATION: ConversationSnapshot = Object.freeze({ entries: Object.freeze([]), activeLogicalSendId: null, announcement: null, revision: 0 });

function ConversationViewport(props: Readonly<{
  botName: string;
  config: PublicWidgetConfigResponse;
  conversation: ConversationSnapshot;
  onSuggestionSelect?: (id: string) => void;
  onRetry?: (logicalSendId: string) => void;
}>) {
  const viewportRef = useRef<HTMLElement>(null);
  const [showJump, setShowJump] = useState(false);
  const [lastAnnouncement, setLastAnnouncement] = useState<string | null>(null);
  const entries = props.conversation.entries;
  const hasConversation = entries.length > 0;
  const suggestions = useMemo(() => deriveSuggestions(props.config), [props.config]);
  const busy = props.conversation.activeLogicalSendId !== null;

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const nearBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
    if (nearBottom || !showJump) {
      scrollViewport(viewport, viewport.scrollHeight);
      setShowJump(false);
    } else {
      setShowJump(true);
    }
    if (props.conversation.announcement && props.conversation.announcement !== lastAnnouncement) {
      setLastAnnouncement(props.conversation.announcement);
    }
  }, [props.conversation.revision]);

  function onScroll() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    setShowJump(viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight > 120);
  }

  return (
    <main ref={viewportRef} className="yw-viewport" role="region" aria-label="Chat conversation" onScroll={onScroll}>
      <div className="yw-live-region" aria-live="polite" aria-atomic="true">{lastAnnouncement}</div>
      {!hasConversation ? (
        <WelcomeState config={props.config} botName={props.botName} suggestions={suggestions} busy={busy} onSuggestionSelect={props.onSuggestionSelect} />
      ) : (
        <MessageThread entries={entries} onRetry={props.onRetry} />
      )}
      {showJump ? <button type="button" className="yw-jump" onClick={() => { if (viewportRef.current) scrollViewport(viewportRef.current, viewportRef.current.scrollHeight); setShowJump(false); }}>Jump to latest</button> : null}
    </main>
  );
}

function WelcomeState(props: Readonly<{ config: PublicWidgetConfigResponse; botName: string; suggestions: readonly SuggestedQuestion[]; busy: boolean; onSuggestionSelect?: (id: string) => void }>) {
  const welcome = safeText(props.config.widget.welcome_message, FALLBACK_WELCOME, 420);
  return (
    <section className="yw-welcome" aria-labelledby="yw-welcome-title">
      <div className="yw-welcome__mark" aria-hidden="true"><AssistantIcon /></div>
      <p className="yw-welcome__eyebrow">Source-grounded AI assistant</p>
      <h2 id="yw-welcome-title" className="yw-welcome__title">Ask {props.botName}</h2>
      <PlainText as="p" className="yw-welcome__message" text={welcome} />
      <p className="yw-welcome__hint">I’ll use the information this organisation has made available for this chat.</p>
      <SuggestedQuestionGroup suggestions={props.suggestions} busy={props.busy} onSelect={props.onSuggestionSelect} />
    </section>
  );
}

function SuggestedQuestionGroup(props: Readonly<{ suggestions: readonly SuggestedQuestion[]; busy: boolean; onSelect?: (id: string) => void }>) {
  if (props.suggestions.length === 0) return null;
  return (
    <div className="yw-suggestions" role="group" aria-label="Suggested questions">
      {props.suggestions.map((suggestion) => (
        <button key={suggestion.id} type="button" className="yw-suggestion" disabled={props.busy} aria-busy={props.busy} onClick={() => props.onSelect?.(suggestion.id)}>
          <span className="yw-suggestion__text">{suggestion.text}</span>
          <span className="yw-suggestion__icon" aria-hidden="true"><ArrowIcon /></span>
        </button>
      ))}
    </div>
  );
}

function MessageThread(props: Readonly<{ entries: readonly ConversationEntry[]; onRetry?: (logicalSendId: string) => void }>) {
  return (
    <ol className="yw-thread" aria-label="Current conversation">
      {props.entries.map((entry) => <ConversationEntryView key={entry.id} entry={entry} onRetry={props.onRetry} />)}
    </ol>
  );
}

function ConversationEntryView(props: Readonly<{ entry: ConversationEntry; onRetry?: (logicalSendId: string) => void }>) {
  if (props.entry.role === "system") return <SystemNotice entry={props.entry} />;
  if (props.entry.role === "user") return <UserMessage entry={props.entry} onRetry={props.onRetry} />;
  return <AssistantMessage entry={props.entry} onRetry={props.onRetry} />;
}

function UserMessage(props: Readonly<{ entry: ConversationEntry; onRetry?: (logicalSendId: string) => void }>) {
  const failed = props.entry.status === "failed";
  return (
    <li className="yw-message yw-message--user" data-status={props.entry.status}>
      <article className="yw-message__bubble" aria-label="You said">
        <PlainText as="p" className="yw-message__text" text={props.entry.content} />
        <MessageMeta>{failed ? "Not sent" : props.entry.status === "sending" ? "Sending" : "Sent"}</MessageMeta>
        {failed && props.entry.retry?.retryable ? <RetryButton logicalSendId={props.entry.retry.logicalSendId} onRetry={props.onRetry} /> : null}
      </article>
    </li>
  );
}

function AssistantMessage(props: Readonly<{ entry: ConversationEntry; onRetry?: (logicalSendId: string) => void }>) {
  const state = props.entry.status;
  const label = assistantStateLabel(state);
  return (
    <li className="yw-message yw-message--assistant" data-status={state}>
      <article className="yw-message__bubble" aria-label="Assistant response">
        <div className="yw-answer-state"><span aria-hidden="true">{stateIcon(state)}</span><span>{label}</span></div>
        {state === "preparing" ? <PreparingState /> : <PlainText as="p" className="yw-message__text" text={props.entry.content} />}
        {props.entry.citations && props.entry.citations.length > 0 ? <p className="yw-citation-placeholder">Sources available</p> : null}
        {state === "failed" && props.entry.retry?.retryable ? <RetryButton logicalSendId={props.entry.retry.logicalSendId} onRetry={props.onRetry} /> : null}
      </article>
    </li>
  );
}

function PreparingState() {
  return (
    <div className="yw-preparing" role="status" aria-live="polite">
      <span className="yw-preparing__line" aria-hidden="true" />
      <span>Checking the available information</span>
    </div>
  );
}

function SystemNotice(props: Readonly<{ entry: ConversationEntry }>) {
  const role = props.entry.status === "error" || props.entry.status === "unavailable" ? "alert" : "status";
  return (
    <li className="yw-system-notice" data-category={props.entry.status}>
      <div role={role} className="yw-system-notice__body"><WarningIcon /> <PlainText as="span" text={props.entry.content} /></div>
    </li>
  );
}

function RetryButton(props: Readonly<{ logicalSendId: string; onRetry?: (logicalSendId: string) => void }>) {
  return <button type="button" className="yw-retry" onClick={() => props.onRetry?.(props.logicalSendId)}><RetryIcon /> Retry</button>;
}

function MessageMeta({ children }: Readonly<{ children: ComponentChildren }>) {
  return <p className="yw-message__meta">{children}</p>;
}

export function WidgetLoadingState() {
  return <div className="yw-empty" role="status" aria-live="polite">Loading widget...</div>;
}

export function WidgetUnavailableState() {
  return (
    <div className="yw-unavailable" role="alert">
      <p className="yw-unavailable__title">Widget unavailable</p>
      <p className="yw-unavailable__body">The assistant cannot be loaded right now.</p>
    </div>
  );
}

function WidgetFooterShell() {
  return <footer className="yw-footer" aria-label="Chat controls area" />;
}

function PlainText(props: Readonly<{ text: string; className?: string; as?: "p" | "span" }>) {
  const Tag = props.as ?? "span";
  const text = boundPlainText(props.text);
  return <Tag className={props.className}>{text}</Tag>;
}

function LauncherGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M5 7.8C5 5.7 6.7 4 8.8 4h6.4C17.3 4 19 5.7 19 7.8v4.8c0 2.1-1.7 3.8-3.8 3.8h-2.5l-3.2 2.4c-.6.4-1.4 0-1.4-.7v-1.8C6.3 16 5 14.4 5 12.6V7.8Z" fill="currentColor" />
    </svg>
  );
}

function AssistantIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M12 3 19 7v7.8L12 21l-7-6.2V7l7-4Zm0 3.1L7.7 8.5v5.1L12 17.4l4.3-3.8V8.5L12 6.1Z" fill="currentColor" /></svg>; }
function ArrowIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M5 12h12m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }
function WarningIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M12 4 3 20h18L12 4Zm0 5v5m0 3h.01" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }
function RetryIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }

function assistantStateLabel(state: ConversationEntry["status"]): string {
  if (state === "fallback") return "Fallback answer";
  if (state === "low_confidence") return "Low confidence";
  if (state === "failed") return "Answer unavailable";
  if (state === "preparing") return "Preparing";
  return "Answer";
}

function stateIcon(state: ConversationEntry["status"]): string {
  if (state === "fallback") return "!";
  if (state === "low_confidence") return "?";
  if (state === "failed") return "!";
  return "•";
}

function safeText(value: unknown, fallback: string, maxLength: number): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.replace(/\u0000/g, "").trim();
  return trimmed.length > 0 ? trimmed.slice(0, maxLength) : fallback;
}

function boundPlainText(value: string): string {
  return value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").replace(/\n{4,}/g, "\n\n\n").slice(0, 8000);
}

function normalisePosition(value: unknown): "left" | "right" {
  return typeof value === "string" && value.toLowerCase().includes("left") ? "left" : "right";
}

function scrollViewport(viewport: HTMLElement, top: number): void {
  if (typeof viewport.scrollTo === "function") {
    viewport.scrollTo({ top, behavior: reducedMotion() ? "auto" : "smooth" });
    return;
  }
  viewport.scrollTop = top;
}

function reducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
