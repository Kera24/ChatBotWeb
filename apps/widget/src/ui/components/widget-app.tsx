import type { ComponentChildren } from "preact";
import type { PublicWidgetConfigResponse } from "../../api/contracts";
import { SafeRasterAsset } from "../assets/safe-raster-asset";
import { WidgetRenderErrorBoundary } from "./error-boundary";
import type { WidgetStateSnapshot } from "../../state/widget-state";

export type WidgetShellState = "loading" | "closed" | "open" | "unavailable" | "destroyed";

export type WidgetAppProps = Readonly<{
  shellState: WidgetShellState;
  snapshot: WidgetStateSnapshot | null;
  systemDark: boolean;
  onOpen?: () => void;
  onClose?: () => void;
  onRenderError?: () => void;
}>;

const FALLBACK_BOT_NAME = "Yoranix assistant";
const FALLBACK_LAUNCHER_LABEL = "Open chat";

export function WidgetApp(props: WidgetAppProps) {
  const config = props.snapshot?.config.data ?? null;
  const botName = safeText(config?.widget.bot_name, FALLBACK_BOT_NAME);
  const launcherLabel = safeText(config?.widget.launcher_label, FALLBACK_LAUNCHER_LABEL);
  const position = normalisePosition(config?.widget.position);
  const isOpen = props.shellState === "open";
  const isUnavailable = props.shellState === "unavailable" || props.snapshot?.bootstrapStatus === "unavailable";

  return (
    <WidgetRenderErrorBoundary onError={props.onRenderError}>
      <WidgetRoot shellState={props.shellState} position={position}>
        <WidgetLauncher label={launcherLabel} isOpen={isOpen} unavailable={isUnavailable} onToggle={isOpen ? props.onClose : props.onOpen} />
        {isOpen ? <WidgetPanel botName={botName} config={config} unavailable={isUnavailable} onClose={props.onClose} /> : null}
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

function WidgetPanel(props: Readonly<{ botName: string; config: PublicWidgetConfigResponse | null; unavailable: boolean; onClose?: () => void }>) {
  return (
    <section className="yw-panel" role="dialog" aria-modal="false" aria-labelledby="yw-panel-title">
      <WidgetHeader botName={props.botName} config={props.config} onClose={props.onClose} />
      <WidgetStatusRegion unavailable={props.unavailable} ready={Boolean(props.config)} />
      <WidgetViewport unavailable={props.unavailable} ready={Boolean(props.config)} botName={props.botName} />
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
  return <div className="yw-status yw-status--ready" role="status" aria-live="polite">Widget ready</div>;
}

function WidgetViewport(props: Readonly<{ unavailable: boolean; ready: boolean; botName: string }>) {
  return (
    <main className="yw-viewport" role="region" aria-label="Chat conversation">
      {props.unavailable ? <WidgetUnavailableState /> : props.ready ? <WidgetShellReadyState botName={props.botName} /> : <WidgetLoadingState />}
    </main>
  );
}

export function WidgetLoadingState() {
  return <div className="yw-empty" role="status" aria-live="polite">Loading widget...</div>;
}

function WidgetShellReadyState({ botName }: Readonly<{ botName: string }>) {
  return (
    <div className="yw-empty" data-testid="widget-shell-ready">
      <p className="yw-empty__eyebrow">Ready</p>
      <p className="yw-empty__title">{botName}</p>
      <p className="yw-empty__body">The conversation interface is being prepared.</p>
    </div>
  );
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

function LauncherGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
      <path d="M5 7.8C5 5.7 6.7 4 8.8 4h6.4C17.3 4 19 5.7 19 7.8v4.8c0 2.1-1.7 3.8-3.8 3.8h-2.5l-3.2 2.4c-.6.4-1.4 0-1.4-.7v-1.8C6.3 16 5 14.4 5 12.6V7.8Z" fill="currentColor" />
    </svg>
  );
}

function safeText(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed.slice(0, 80) : fallback;
}

function normalisePosition(value: unknown): "left" | "right" {
  return typeof value === "string" && value.toLowerCase().includes("left") ? "left" : "right";
}
