import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import type { ComponentChildren, RefObject } from "preact";
import type { PublicCitation, PublicWidgetConfigResponse } from "../../api/contracts";
import type { ConversationEntry, ConversationSnapshot } from "../../state/conversation-state";
import { CHARACTER_COUNT_NOTICE_RATIO, deriveSuggestions, PUBLIC_MESSAGE_MAX_CHARACTERS, validateComposerMessage, type SuggestedQuestion } from "../../services/conversation-orchestrator";
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
  onSubmitMessage?: (message: string) => Promise<void> | void;
  onRetry?: (logicalSendId: string) => void;
  onRenderError?: () => void;
}>;

type ConnectivityState = "online" | "offline" | "reconnecting";

type ComposerState = Readonly<{
  value: string;
  isImeComposing: boolean;
  validationMessage: string | null;
}>;

const FALLBACK_BOT_NAME = "Yoranix assistant";
const FALLBACK_LAUNCHER_LABEL = "Open chat";
const FALLBACK_WELCOME = "Ask a question and I'll check the available information.";
const COUNT_NOTICE_THRESHOLD = Math.floor(PUBLIC_MESSAGE_MAX_CHARACTERS * CHARACTER_COUNT_NOTICE_RATIO);

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
      <span className="yw-launcher__mark" aria-hidden="true">{props.isOpen ? "x" : <LauncherGlyph />}</span>
      <span className="yw-launcher__label">{props.isOpen ? "Close" : props.label}</span>
    </button>
  );
}

function WidgetPanel(props: WidgetAppProps & Readonly<{ botName: string; config: PublicWidgetConfigResponse | null; unavailable: boolean }>) {
  const panelRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  function onPanelKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape" && !event.isComposing) {
      event.preventDefault();
      props.onClose?.();
      return;
    }
    if (event.key === "Tab" && panelRef.current) trapTabWithin(panelRef.current, event);
  }

  return (
    <section ref={panelRef} className="yw-panel" role="dialog" aria-modal="false" aria-labelledby="yw-panel-title" onKeyDown={onPanelKeyDown}>
      <WidgetHeader headingRef={headingRef} botName={props.botName} config={props.config} onClose={props.onClose} />
      <WidgetStatusRegion unavailable={props.unavailable} ready={Boolean(props.config)} />
      <WidgetViewport
        unavailable={props.unavailable}
        ready={Boolean(props.config)}
        botName={props.botName}
        config={props.config}
        snapshot={props.snapshot}
        conversation={props.conversation}
        onSuggestionSelect={props.onSuggestionSelect}
        onSubmitMessage={props.onSubmitMessage}
        onRetry={props.onRetry}
      />
    </section>
  );
}

function WidgetHeader(props: Readonly<{ headingRef: RefObject<HTMLHeadingElement>; botName: string; config: PublicWidgetConfigResponse | null; onClose?: () => void }>) {
  return (
    <header className="yw-header">
      <div className="yw-header__avatar" aria-hidden="true">
        <SafeRasterAsset src={props.config?.widget.avatar_url ?? props.config?.widget.logo_url ?? null} alt="" className="yw-header__avatar-img" />
      </div>
      <div className="yw-header__identity">
        <h1 ref={props.headingRef} id="yw-panel-title" className="yw-header__title" tabIndex={-1}>{props.botName}</h1>
        <p className="yw-header__status">AI assistant</p>
      </div>
      <button type="button" className="yw-header__close" aria-label="Close chat" onClick={props.onClose}>x</button>
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
  snapshot: WidgetStateSnapshot | null;
  conversation?: ConversationSnapshot | null;
  onSuggestionSelect?: (id: string) => void;
  onSubmitMessage?: (message: string) => Promise<void> | void;
  onRetry?: (logicalSendId: string) => void;
}>) {
  if (props.unavailable) return <main className="yw-viewport" role="region" aria-label="Chat conversation"><WidgetUnavailableState /></main>;
  if (!props.ready || !props.config) return <main className="yw-viewport" role="region" aria-label="Chat conversation"><WidgetLoadingState /></main>;
  return <ConversationExperience {...props} config={props.config} conversation={props.conversation ?? EMPTY_CONVERSATION} snapshot={props.snapshot} />;
}

const EMPTY_CONVERSATION: ConversationSnapshot = Object.freeze({ entries: Object.freeze([]), activeLogicalSendId: null, announcement: null, revision: 0 });

function ConversationExperience(props: Readonly<{
  botName: string;
  config: PublicWidgetConfigResponse;
  snapshot: WidgetStateSnapshot | null;
  conversation: ConversationSnapshot;
  onSuggestionSelect?: (id: string) => void;
  onSubmitMessage?: (message: string) => Promise<void> | void;
  onRetry?: (logicalSendId: string) => void;
}>) {
  const connectivity = useConnectivityState();
  const [composer, setComposer] = useState<ComposerState>({ value: "", isImeComposing: false, validationMessage: null });
  const [rateUntil, setRateUntil] = useState<number | null>(null);
  const retryAfter = props.snapshot?.lastError?.code === "rate_limited" ? props.snapshot.lastError.retryAfterSeconds ?? null : null;
  const rateRemaining = useCountdown(rateUntil);
  const entries = props.conversation.entries;
  const busy = props.conversation.activeLogicalSendId !== null;
  const sessionRemaining = props.snapshot?.session.remainingMessages ?? null;
  const sessionStatus = props.snapshot?.session.status ?? "none";
  const blockedBySessionLimit = sessionStatus === "expired" || sessionStatus === "invalid" || sessionRemaining === 0;
  const sendDisabledReason = disabledReason(connectivity, busy, rateRemaining, blockedBySessionLimit, sessionRemaining);

  useEffect(() => {
    if (retryAfter && retryAfter > 0) setRateUntil(Date.now() + retryAfter * 1000);
  }, [retryAfter]);

  async function submitComposer() {
    const validation = validateComposerMessage(composer.value);
    if (!validation.ok) {
      setComposer((current) => ({ ...current, validationMessage: validation.message }));
      return;
    }
    if (sendDisabledReason) return;
    const acceptedValue = validation.value;
    setComposer((current) => ({ ...current, value: "", validationMessage: null }));
    try {
      await props.onSubmitMessage?.(acceptedValue);
    } catch {
      setComposer((current) => ({ ...current, value: acceptedValue }));
    }
  }

  return (
    <>
      <ConversationViewport
        botName={props.botName}
        config={props.config}
        conversation={props.conversation}
        connectivity={connectivity}
        rateRemaining={rateRemaining}
        sessionRemaining={sessionRemaining}
        sessionStatus={sessionStatus}
        onSuggestionSelect={props.onSuggestionSelect}
        onRetry={props.onRetry}
      />
      <ComposerFooter
        config={props.config}
        value={composer.value}
        isImeComposing={composer.isImeComposing}
        validationMessage={composer.validationMessage}
        busy={busy}
        disabledReason={sendDisabledReason}
        connectivity={connectivity}
        onValueChange={(value) => setComposer((current) => ({ ...current, value, validationMessage: null }))}
        onImeChange={(isImeComposing) => setComposer((current) => ({ ...current, isImeComposing }))}
        onSubmit={submitComposer}
      />
    </>
  );
}

function ConversationViewport(props: Readonly<{
  botName: string;
  config: PublicWidgetConfigResponse;
  conversation: ConversationSnapshot;
  connectivity: ConnectivityState;
  rateRemaining: number | null;
  sessionRemaining: number | null;
  sessionStatus: string;
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
    if (props.conversation.announcement && props.conversation.announcement !== lastAnnouncement) setLastAnnouncement(props.conversation.announcement);
  }, [props.conversation.revision]);

  useEffect(() => {
    if (props.connectivity === "offline") setLastAnnouncement("You are offline. Reconnect to send your message.");
    if (props.connectivity === "reconnecting") setLastAnnouncement("Connection restored. You can send again.");
  }, [props.connectivity]);

  useEffect(() => {
    if (props.rateRemaining && props.rateRemaining > 0) setLastAnnouncement(`Please wait ${props.rateRemaining} seconds before sending.`);
    if (props.rateRemaining === 0) setLastAnnouncement("You can send again.");
  }, [props.rateRemaining === null ? null : props.rateRemaining > 0 ? "active" : "done"]);

  function onScroll() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    setShowJump(viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight > 120);
  }

  return (
    <main ref={viewportRef} className="yw-viewport" role="region" aria-label="Chat conversation" onScroll={onScroll}>
      <div className="yw-live-region" aria-live="polite" aria-atomic="true">{lastAnnouncement}</div>
      <ConversationNotices connectivity={props.connectivity} rateRemaining={props.rateRemaining} sessionRemaining={props.sessionRemaining} sessionStatus={props.sessionStatus} />
      {!hasConversation ? (
        <WelcomeState config={props.config} botName={props.botName} suggestions={suggestions} busy={busy} onSuggestionSelect={props.onSuggestionSelect} />
      ) : (
        <MessageThread entries={entries} onRetry={props.onRetry} showCitations={props.config.behaviour.show_citations && props.config.capabilities.citations_enabled} />
      )}
      {showJump ? <button type="button" className="yw-jump" onClick={() => { if (viewportRef.current) scrollViewport(viewportRef.current, viewportRef.current.scrollHeight); setShowJump(false); }}>Jump to latest</button> : null}
    </main>
  );
}

function ConversationNotices(props: Readonly<{ connectivity: ConnectivityState; rateRemaining: number | null; sessionRemaining: number | null; sessionStatus: string }>) {
  return (
    <div className="yw-notices" aria-live="polite">
      {props.connectivity === "offline" ? <Notice kind="warning">You're offline. Reconnect to send your message.</Notice> : null}
      {props.rateRemaining && props.rateRemaining > 0 ? <Notice kind="warning">Please wait {props.rateRemaining} seconds before sending another message.</Notice> : null}
      {props.sessionStatus === "expired" || props.sessionStatus === "invalid" ? <Notice kind="error">This chat session ended. Send again to start a fresh session.</Notice> : null}
      {props.sessionRemaining === 0 ? <Notice kind="error">This chat has reached its message limit.</Notice> : props.sessionRemaining !== null && props.sessionRemaining <= 3 ? <Notice kind="warning">You have {props.sessionRemaining} message{props.sessionRemaining === 1 ? "" : "s"} left in this session.</Notice> : null}
    </div>
  );
}

function Notice(props: Readonly<{ kind: "warning" | "error"; children: ComponentChildren }>) {
  return <div className={`yw-inline-notice yw-inline-notice--${props.kind}`} role={props.kind === "error" ? "alert" : "status"}>{props.children}</div>;
}

function WelcomeState(props: Readonly<{ config: PublicWidgetConfigResponse; botName: string; suggestions: readonly SuggestedQuestion[]; busy: boolean; onSuggestionSelect?: (id: string) => void }>) {
  const welcome = safeText(props.config.widget.welcome_message, FALLBACK_WELCOME, 420);
  return (
    <section className="yw-welcome" aria-labelledby="yw-welcome-title">
      <div className="yw-welcome__mark" aria-hidden="true"><AssistantIcon /></div>
      <p className="yw-welcome__eyebrow">Source-grounded AI assistant</p>
      <h2 id="yw-welcome-title" className="yw-welcome__title">Ask {props.botName}</h2>
      <PlainText as="p" className="yw-welcome__message" text={welcome} />
      <p className="yw-welcome__hint">I'll use the information this organisation has made available for this chat.</p>
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

function MessageThread(props: Readonly<{ entries: readonly ConversationEntry[]; onRetry?: (logicalSendId: string) => void; showCitations: boolean }>) {
  return <ol className="yw-thread" aria-label="Current conversation">{props.entries.map((entry) => <ConversationEntryView key={entry.id} entry={entry} onRetry={props.onRetry} showCitations={props.showCitations} />)}</ol>;
}

function ConversationEntryView(props: Readonly<{ entry: ConversationEntry; onRetry?: (logicalSendId: string) => void; showCitations: boolean }>) {
  if (props.entry.role === "system") return <SystemNotice entry={props.entry} />;
  if (props.entry.role === "user") return <UserMessage entry={props.entry} onRetry={props.onRetry} />;
  return <AssistantMessage entry={props.entry} onRetry={props.onRetry} showCitations={props.showCitations} />;
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

function AssistantMessage(props: Readonly<{ entry: ConversationEntry; onRetry?: (logicalSendId: string) => void; showCitations: boolean }>) {
  const state = props.entry.status;
  const label = assistantStateLabel(state);
  const citations = props.showCitations && state !== "fallback" ? safeCitations(props.entry.citations) : [];
  return (
    <li className="yw-message yw-message--assistant" data-status={state}>
      <article className="yw-message__bubble" aria-label="Assistant response">
        <div className="yw-answer-state"><span aria-hidden="true">{stateIcon(state)}</span><span>{label}</span></div>
        {state === "preparing" ? <PreparingState /> : <PlainText as="p" className="yw-message__text" text={props.entry.content} />}
        {citations.length > 0 ? <CitationDisclosure citations={citations} /> : null}
        {state === "failed" && props.entry.retry?.retryable ? <RetryButton logicalSendId={props.entry.retry.logicalSendId} onRetry={props.onRetry} /> : null}
      </article>
    </li>
  );
}

function CitationDisclosure(props: Readonly<{ citations: readonly PublicCitation[] }>) {
  return (
    <details className="yw-citations">
      <summary>Sources ({props.citations.length})</summary>
      <ol className="yw-citations__list">
        {props.citations.map((citation) => <CitationItem key={`${citation.citation_index}-${citation.source_title}`} citation={citation} />)}
      </ol>
    </details>
  );
}

function CitationItem(props: Readonly<{ citation: PublicCitation }>) {
  const meta = [props.citation.source_type, props.citation.page_number ? `page ${props.citation.page_number}` : null, props.citation.section_title].filter(Boolean).join(" · ");
  return (
    <li className="yw-citation-item">
      <p className="yw-citation-item__title"><span aria-hidden="true">[{props.citation.citation_index}]</span> {boundPlainText(props.citation.source_title)}</p>
      {meta ? <p className="yw-citation-item__meta">{boundPlainText(meta)}</p> : null}
      {props.citation.quoted_text ? <PlainText as="p" className="yw-citation-item__quote" text={props.citation.quoted_text} /> : null}
    </li>
  );
}

function PreparingState() {
  return <div className="yw-preparing" role="status" aria-live="polite"><span className="yw-preparing__line" aria-hidden="true" /><span>Checking the available information</span></div>;
}

function SystemNotice(props: Readonly<{ entry: ConversationEntry }>) {
  const role = props.entry.status === "error" || props.entry.status === "unavailable" ? "alert" : "status";
  return <li className="yw-system-notice" data-category={props.entry.status}><div role={role} className="yw-system-notice__body"><WarningIcon /> <PlainText as="span" text={props.entry.content} /></div></li>;
}

function RetryButton(props: Readonly<{ logicalSendId: string; onRetry?: (logicalSendId: string) => void }>) {
  return <button type="button" className="yw-retry" aria-label="Retry message" onClick={() => props.onRetry?.(props.logicalSendId)}><RetryIcon /> Retry</button>;
}

function ComposerFooter(props: Readonly<{
  config: PublicWidgetConfigResponse;
  value: string;
  isImeComposing: boolean;
  validationMessage: string | null;
  busy: boolean;
  disabledReason: string | null;
  connectivity: ConnectivityState;
  onValueChange: (value: string) => void;
  onImeChange: (isImeComposing: boolean) => void;
  onSubmit: () => void;
}>) {
  const validation = validateComposerMessage(props.value);
  const charCount = props.value.length;
  const showCount = charCount >= COUNT_NOTICE_THRESHOLD || !validation.ok && validation.overLimit;
  const validationMessage = props.validationMessage ?? (!validation.ok && props.value.trim() ? validation.message : null);
  const sendDisabled = props.busy || Boolean(props.disabledReason) || !validation.ok;
  const describedBy = [validationMessage ? "yw-composer-error" : null, props.disabledReason ? "yw-composer-status" : null, showCount ? "yw-composer-count" : null].filter(Boolean).join(" ") || undefined;

  function onKeyDown(event: KeyboardEvent) {
    if (event.key !== "Enter" || event.shiftKey || props.isImeComposing) return;
    event.preventDefault();
    props.onSubmit();
  }

  return (
    <footer className="yw-footer" aria-label="Chat controls">
      <PrivacyFooter config={props.config} compact={false} />
      <form className="yw-composer" aria-label="Send a message" onSubmit={(event) => { event.preventDefault(); props.onSubmit(); }}>
        <label className="yw-composer__label" htmlFor="yw-composer-input">Message</label>
        <textarea
          id="yw-composer-input"
          className="yw-composer__field"
          rows={1}
          value={props.value}
          maxLength={PUBLIC_MESSAGE_MAX_CHARACTERS + 500}
          aria-invalid={validationMessage ? "true" : "false"}
          aria-describedby={describedBy}
          placeholder={props.connectivity === "offline" ? "Reconnect to send" : "Ask a question..."}
          disabled={false}
          onInput={(event) => props.onValueChange((event.currentTarget as HTMLTextAreaElement).value)}
          onKeyDown={onKeyDown}
          onCompositionStart={() => props.onImeChange(true)}
          onCompositionEnd={() => props.onImeChange(false)}
        />
        <div className="yw-composer__meta">
          {validationMessage ? <p id="yw-composer-error" className="yw-composer__error" role="alert">{validationMessage}</p> : null}
          {props.disabledReason ? <p id="yw-composer-status" className="yw-composer__status">{props.disabledReason}</p> : null}
          {showCount ? <p id="yw-composer-count" className="yw-composer__count">{charCount}/{PUBLIC_MESSAGE_MAX_CHARACTERS}</p> : null}
        </div>
        <button type="submit" className="yw-send" disabled={sendDisabled} aria-label={props.busy ? "Sending message" : "Send message"}><SendIcon /></button>
      </form>
    </footer>
  );
}

function PrivacyFooter(props: Readonly<{ config: PublicWidgetConfigResponse; compact: boolean }>) {
  const text = safeText(props.config.privacy.privacy_notice_text, "Avoid sharing sensitive personal information in this chat.", 180);
  const privacy = safeHttpsUrl(props.config.privacy.privacy_notice_url);
  const terms = safeHttpsUrl(props.config.privacy.terms_url);
  return (
    <div className="yw-privacy" aria-label="Privacy information">
      <PlainText as="span" text={text} />
      {privacy ? <a href={privacy} target="_blank" rel="noopener noreferrer">Privacy</a> : null}
      {terms ? <a href={terms} target="_blank" rel="noopener noreferrer">Terms</a> : null}
    </div>
  );
}

function MessageMeta({ children }: Readonly<{ children: ComponentChildren }>) { return <p className="yw-message__meta">{children}</p>; }
export function WidgetLoadingState() { return <div className="yw-empty" role="status" aria-live="polite">Loading widget...</div>; }
export function WidgetUnavailableState() { return <div className="yw-unavailable" role="alert"><p className="yw-unavailable__title">Widget unavailable</p><p className="yw-unavailable__body">The assistant cannot be loaded right now.</p></div>; }

function PlainText(props: Readonly<{ text: string; className?: string; as?: "p" | "span" }>) {
  const Tag = props.as ?? "span";
  return <Tag className={props.className}>{boundPlainText(props.text)}</Tag>;
}
function LauncherGlyph() { return <svg width="22" height="22" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M5 7.8C5 5.7 6.7 4 8.8 4h6.4C17.3 4 19 5.7 19 7.8v4.8c0 2.1-1.7 3.8-3.8 3.8h-2.5l-3.2 2.4c-.6.4-1.4 0-1.4-.7v-1.8C6.3 16 5 14.4 5 12.6V7.8Z" fill="currentColor" /></svg>; }
function AssistantIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M12 3 19 7v7.8L12 21l-7-6.2V7l7-4Zm0 3.1L7.7 8.5v5.1L12 17.4l4.3-3.8V8.5L12 6.1Z" fill="currentColor" /></svg>; }
function ArrowIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M5 12h12m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }
function WarningIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M12 4 3 20h18L12 4Zm0 5v5m0 3h.01" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }
function RetryIcon() { return <svg width="15" height="15" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }
function SendIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="m4 12 15-7-4 14-3-5-5-2Zm8 2 7-9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>; }

function assistantStateLabel(state: ConversationEntry["status"]): string {
  if (state === "fallback") return "Fallback answer";
  if (state === "low_confidence") return "Low confidence";
  if (state === "failed") return "Answer unavailable";
  if (state === "preparing") return "Preparing";
  return "Answer";
}
function stateIcon(state: ConversationEntry["status"]): string { if (state === "fallback") return "!"; if (state === "low_confidence") return "?"; if (state === "failed") return "!"; return "-"; }

function useConnectivityState(): ConnectivityState {
  const [state, setState] = useState<ConnectivityState>(() => typeof navigator !== "undefined" && navigator.onLine === false ? "offline" : "online");
  useEffect(() => {
    const offline = () => setState("offline");
    const online = () => { setState("reconnecting"); window.setTimeout(() => setState("online"), 400); };
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => { window.removeEventListener("offline", offline); window.removeEventListener("online", online); };
  }, []);
  return state;
}

function useCountdown(until: number | null): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);
  useEffect(() => {
    if (!until) { setRemaining(null); return; }
    const update = () => setRemaining(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return remaining;
}

function disabledReason(connectivity: ConnectivityState, busy: boolean, rateRemaining: number | null, blockedBySessionLimit: boolean, remainingMessages: number | null): string | null {
  if (connectivity === "offline") return "You're offline. Reconnect to send.";
  if (busy) return "Waiting for the current answer.";
  if (rateRemaining && rateRemaining > 0) return `Wait ${rateRemaining} seconds before sending again.`;
  if (blockedBySessionLimit) return remainingMessages === 0 ? "This chat has reached its message limit." : "This chat session ended. Try again to start a fresh session.";
  return null;
}

function safeCitations(citations: readonly PublicCitation[] | undefined): readonly PublicCitation[] {
  if (!citations) return [];
  return citations.filter((citation) => citation.citation_index > 0 && citation.source_title && citation.source_title.length <= 240 && !containsUnsafePath(citation.source_title)).slice(0, 5);
}
function containsUnsafePath(value: string): boolean { return /([A-Za-z]:\\|\/var\/|\/home\/|s3:\/\/|file:\/\/)/.test(value); }
function safeText(value: unknown, fallback: string, maxLength: number): string { if (typeof value !== "string") return fallback; const trimmed = value.replace(/\u0000/g, "").trim(); return trimmed.length > 0 ? trimmed.slice(0, maxLength) : fallback; }
function boundPlainText(value: string): string { return value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").replace(/\n{4,}/g, "\n\n\n").slice(0, 8000); }
function normalisePosition(value: unknown): "left" | "right" { return typeof value === "string" && value.toLowerCase().includes("left") ? "left" : "right"; }
function safeHttpsUrl(value: unknown): string | null { if (typeof value !== "string") return null; try { const url = new URL(value); if (url.protocol !== "https:" || url.username || url.password) return null; return url.toString(); } catch { return null; } }
function scrollViewport(viewport: HTMLElement, top: number): void { if (typeof viewport.scrollTo === "function") { viewport.scrollTo({ top, behavior: reducedMotion() ? "auto" : "smooth" }); return; } viewport.scrollTop = top; }
function reducedMotion(): boolean { return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
function focusableElements(root: HTMLElement): HTMLElement[] { return Array.from(root.querySelectorAll<HTMLElement>('button:not([disabled]), textarea:not([disabled]), a[href], summary, [tabindex]:not([tabindex="-1"])')).filter((el) => !el.hasAttribute("hidden") && el.offsetParent !== null); }
function trapTabWithin(root: HTMLElement, event: KeyboardEvent): void { const elements = focusableElements(root); if (elements.length === 0) return; const first = elements[0]; const last = elements[elements.length - 1]; const active = document.activeElement; if (event.shiftKey && active === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && active === last) { event.preventDefault(); first.focus(); } }
