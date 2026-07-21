import Link from "next/link";

import type { WidgetEmbedMetadata, WidgetSummary } from "../../lib/api/widgets";

export function WidgetStatusBadge({ label, value }: { label: string; value: string | null | undefined }) {
  const normalised = (value || "unknown").replace(/_/g, " ");
  return (
    <span className={`widgetStatusBadge widget-status-${value || "unknown"}`} aria-label={`${label}: ${normalised}`}>
      <span className="statusBadgeDot" aria-hidden="true" />
      <span>{label}: {normalised}</span>
    </span>
  );
}

export function WidgetReadinessList({ readiness }: { readiness: string[] }) {
  return (
    <ul className="widgetReadinessList" aria-label="Embed readiness">
      {readiness.map((code) => (
        <li key={code}>{readinessMessage(code)}</li>
      ))}
    </ul>
  );
}

export function readinessMessage(code: string) {
  switch (code) {
    case "ready":
      return "Ready for the current pilot policy.";
    case "unpublished":
      return "Publish workflow has not made this widget public yet.";
    case "no_allowed_origins":
      return "Add an allowed domain before the widget can be used.";
    case "pilot_not_enabled":
      return "Published configuration is separate from pilot enablement.";
    case "operationally_disabled":
      return "Widget access is currently disabled.";
    case "unsupported_sdk_version":
      return "The selected SDK version is not currently supported.";
    default:
      return code.replace(/_/g, " ");
  }
}

export function WidgetList({ widgets }: { widgets: WidgetSummary[] }) {
  if (widgets.length === 0) {
    return (
      <section className="statePanel">
        <p className="sectionKicker">No widgets yet</p>
        <h2>Create the first website widget</h2>
        <p>Configure draft settings, allowed domains, and embed details before a later publish workflow makes the widget public.</p>
        <Link className="actionButton" href="/widgets/new">Create widget</Link>
      </section>
    );
  }

  return (
    <div className="widgetList" role="list" aria-label="Workspace widgets">
      {widgets.map((widget) => (
        <article className="widgetRow" role="listitem" key={widget.id}>
          <div className="widgetRowMain">
            <p className="sectionKicker">Widget</p>
            <h2><Link href={`/widgets/${widget.id}`}>{widget.display_name}</Link></h2>
            <p>{widget.draft_dirty ? "Draft has saved changes outside the active published revision." : "Draft matches the current saved state."}</p>
          </div>
          <dl className="widgetFacts">
            <div>
              <dt>Publication</dt>
              <dd><WidgetStatusBadge label="Publication" value={widget.publication_status} /></dd>
            </div>
            <div>
              <dt>Operational</dt>
              <dd><WidgetStatusBadge label="Operational" value={widget.operational_status} /></dd>
            </div>
            <div>
              <dt>Pilot</dt>
              <dd><WidgetStatusBadge label="Pilot" value={widget.pilot_status} /></dd>
            </div>
            <div>
              <dt>Published revision</dt>
              <dd>{widget.active_revision_number ? `Revision ${widget.active_revision_number}` : "None"}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

export function EmbedSummary({ embed }: { embed: WidgetEmbedMetadata | null }) {
  if (!embed) return null;
  return (
    <section className="widgetPanel" aria-labelledby="embed-status-title">
      <h2 id="embed-status-title">Embed status</h2>
      <div className="widgetStatusCluster">
        <WidgetStatusBadge label="Publication" value={embed.publication_status} />
        <WidgetStatusBadge label="Operational" value={embed.operational_status} />
        <WidgetStatusBadge label="Pilot" value={embed.pilot_status} />
      </div>
      <WidgetReadinessList readiness={embed.readiness} />
    </section>
  );
}
