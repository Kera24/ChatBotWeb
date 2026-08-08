"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import {
  type PromptCompositePreview,
  type PromptDeployment,
  type PromptTemplate,
  type PromptVersion,
  createPromptVersion,
  deployPromptVersion,
  evaluatePromptVersion,
  getCompositePromptPreview,
  getPromptDeployment,
  listPromptAuditEvents,
  rollbackPromptDeployment,
  transitionPromptVersion,
} from "../../lib/api/prompts";
import type { WidgetSummary } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type PromptTemplateDetailViewProps = {
  session: DevelopmentDashboardSession;
  template: PromptTemplate;
  versions: PromptVersion[];
  widgets: WidgetSummary[];
  canManage: boolean;
  isSuperAdmin: boolean;
};

const NEXT_STATUS: Record<string, string[]> = {
  draft: ["under_evaluation"],
  under_evaluation: ["approved", "rejected", "draft"],
  approved: ["rejected"],
};

function formatLayer(layer: string): string {
  return layer.replace(/_/g, " ");
}

export function PromptTemplateDetailView({ session, template, versions: initialVersions, widgets, canManage, isSuperAdmin }: PromptTemplateDetailViewProps) {
  const [versions, setVersions] = useState(initialVersions);
  const [widgetId, setWidgetId] = useState(widgets[0]?.id ?? "");
  const [deployment, setDeployment] = useState<PromptDeployment | null>(null);
  const [preview, setPreview] = useState<PromptCompositePreview | null>(null);
  const [content, setContent] = useState("");
  const [changeNotes, setChangeNotes] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [gateVerdicts, setGateVerdicts] = useState<Record<string, { passed: boolean; reasons: string[] }>>({});

  const mayEditContent = canManage && (!template.is_platform_immutable || isSuperAdmin);
  const deployScopeArgs = template.is_platform_immutable ? undefined : widgetId || undefined;

  function resetStatus() {
    setError(null);
    setMessage(null);
  }

  async function refreshDeployment() {
    try {
      const response = await getPromptDeployment(session, template.layer, deployScopeArgs);
      setDeployment(response.data);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not load deployment status.");
    }
  }

  async function loadPreview() {
    setPending("preview");
    resetStatus();
    try {
      const response = await getCompositePromptPreview(session, widgetId || undefined);
      setPreview(response.data);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not render preview.");
    } finally {
      setPending(null);
    }
  }

  async function createDraft() {
    if (!content.trim()) {
      setError("Enter content for the new draft version.");
      return;
    }
    setPending("draft");
    resetStatus();
    try {
      const response = await createPromptVersion(session, template.id, { content: content.trim(), change_notes: changeNotes || undefined });
      setVersions((current) => [response.data, ...current]);
      setContent("");
      setChangeNotes("");
      setMessage(`Draft v${response.data.version_number} created.`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not create draft version.");
    } finally {
      setPending(null);
    }
  }

  async function transition(version: PromptVersion, newStatus: string) {
    setPending(`transition-${version.id}`);
    resetStatus();
    try {
      const response = await transitionPromptVersion(session, version.id, newStatus);
      setVersions((current) => current.map((item) => (item.id === version.id ? response.data : item)));
      setMessage(`v${version.version_number} moved to ${newStatus.replace(/_/g, " ")}.`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not update version status.");
    } finally {
      setPending(null);
    }
  }

  async function runGate(version: PromptVersion) {
    if (!datasetId) {
      setError("Enter an evaluation dataset id before running the gate.");
      return;
    }
    if (!widgetId) {
      setError("Select an assistant before running the gate.");
      return;
    }
    setPending(`gate-${version.id}`);
    resetStatus();
    try {
      const response = await evaluatePromptVersion(session, version.id, datasetId, widgetId);
      setGateVerdicts((current) => ({ ...current, [version.id]: response.data }));
      setMessage(response.data.passed ? `v${version.version_number} passed the evaluation gate.` : `v${version.version_number} failed the evaluation gate.`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not run the evaluation gate.");
    } finally {
      setPending(null);
    }
  }

  async function deploy(version: PromptVersion) {
    setPending(`deploy-${version.id}`);
    resetStatus();
    try {
      const response = await deployPromptVersion(session, version.id, deployScopeArgs);
      setDeployment(response.data);
      setVersions((current) => current.map((item) => (item.id === version.id ? { ...item, status: "active" } : item)));
      setMessage(`v${version.version_number} is now active.`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not deploy this version.");
    } finally {
      setPending(null);
    }
  }

  async function rollback() {
    if (!deployment) return;
    setPending("rollback");
    resetStatus();
    try {
      const response = await rollbackPromptDeployment(session, deployment.id);
      setDeployment(response.data);
      setMessage("Rolled back to the previous version.");
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not roll back this deployment.");
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="observabilityPage" aria-labelledby="prompt-template-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Prompt Management</p>
          <h1 id="prompt-template-title">{template.name}</h1>
          <p className="observabilitySubtitle">
            <span className={`badge ${template.is_platform_immutable ? "severity-critical" : "severity-low"}`}>{formatLayer(template.layer)}</span>
            {template.is_platform_immutable ? " Platform-immutable - only super admins may edit or deploy this layer." : " Workspace-editable layer."}
          </p>
        </div>
        <nav className="observabilityTraceDetailActions" aria-label="Prompt template sections">
          <Link className="smallButton" href={`/prompts/${template.id}/experiments`}>Experiments</Link>
        </nav>
      </header>

      {!widgets.length ? null : (
        <label>
          <span>Assistant (used for deploy/rollback/evaluate/preview scope)</span>
          <select value={widgetId} onChange={(event) => { setWidgetId(event.target.value); setDeployment(null); }} disabled={pending !== null}>
            <option value="">Select an assistant</option>
            {widgets.map((widget) => (
              <option key={widget.id} value={widget.id}>{widget.display_name}</option>
            ))}
          </select>
        </label>
      )}

      <section className="reviewDecisionPanel" aria-labelledby="deployment-status-title">
        <div className="reviewDecisionHeading">
          <div>
            <p className="sectionKicker">Deployment</p>
            <h2 id="deployment-status-title">Current active version</h2>
          </div>
        </div>
        <div className="reviewDecisionActions">
          <button className="smallButton" type="button" disabled={pending !== null} onClick={refreshDeployment}>Check current deployment</button>
          <button className="smallButton" type="button" disabled={pending !== null} onClick={loadPreview}>
            {pending === "preview" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
            Render live preview
          </button>
        </div>
        {deployment ? (
          <div>
            <p>Active version id: <code>{deployment.active_version_id}</code></p>
            {deployment.previous_version_id ? (
              <button className="actionButton" type="button" disabled={pending !== null || (template.is_platform_immutable && !isSuperAdmin)} onClick={rollback}>
                {pending === "rollback" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                Roll back
              </button>
            ) : (
              <p className="mutedText">No previous version to roll back to.</p>
            )}
          </div>
        ) : (
          <p className="mutedText">No deployment checked yet for this scope.</p>
        )}
        {preview ? (
          preview.engaged ? (
            <div>
              <p className="mutedText">Composite version: {preview.version}</p>
              <pre className="mutedText" style={{ whiteSpace: "pre-wrap" }}>{preview.system_prompt}</pre>
            </div>
          ) : (
            <p className="mutedText">Prompt management is dormant for this scope - the default code-defined prompt is used unchanged.</p>
          )
        ) : null}
      </section>

      {mayEditContent ? (
        <section className="reviewDecisionPanel" aria-labelledby="new-draft-title">
          <div className="reviewDecisionHeading">
            <div>
              <p className="sectionKicker">Draft</p>
              <h2 id="new-draft-title">Create a new version</h2>
            </div>
          </div>
          <label>
            <span>Content</span>
            <textarea value={content} onChange={(event) => setContent(event.target.value)} disabled={pending !== null} rows={6} />
          </label>
          <label>
            <span>Change notes</span>
            <input type="text" value={changeNotes} onChange={(event) => setChangeNotes(event.target.value)} disabled={pending !== null} />
          </label>
          <div className="reviewDecisionActions">
            <button className="actionButton" type="button" disabled={pending !== null} onClick={createDraft}>
              {pending === "draft" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
              Create draft
            </button>
          </div>
        </section>
      ) : (
        <p className="mutedText">Version content for this layer is not editable from this account.</p>
      )}

      <section aria-labelledby="version-history-title">
        <p className="sectionKicker" id="version-history-title">Version history</p>
        <div className="observabilityTraceList" role="list">
          {versions.map((version) => {
            const allowedNext = NEXT_STATUS[version.status] ?? [];
            const gate = gateVerdicts[version.id];
            return (
              <div className="card" role="listitem" key={version.id}>
                <div className="reviewDecisionHeading">
                  <div>
                    <p>v{version.version_number} <span className={`badge answerState-${version.status}`}>{version.status.replace(/_/g, " ")}</span></p>
                    {version.change_notes ? <p className="mutedText">{version.change_notes}</p> : null}
                  </div>
                </div>
                {version.content_visibility === "full" && version.content !== null ? (
                  <pre className="mutedText" style={{ whiteSpace: "pre-wrap" }}>{version.content}</pre>
                ) : (
                  <p className="mutedText">Content hidden - platform-immutable layer, super admin required to view.</p>
                )}
                {gate ? (
                  <p className={gate.passed ? "mutedText" : "errorText"}>
                    Gate: {gate.passed ? "PASSED" : "FAILED"}{gate.reasons.length ? ` - ${gate.reasons.join("; ")}` : ""}
                  </p>
                ) : null}
                {canManage ? (
                  <div className="reviewDecisionActions">
                    {allowedNext.map((nextStatus) => (
                      <button
                        key={nextStatus}
                        className="smallButton"
                        type="button"
                        disabled={pending !== null || (template.is_platform_immutable && !isSuperAdmin)}
                        onClick={() => transition(version, nextStatus)}
                      >
                        {pending === `transition-${version.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                        Move to {nextStatus.replace(/_/g, " ")}
                      </button>
                    ))}
                    {version.status === "under_evaluation" || version.status === "draft" ? (
                      <button className="smallButton" type="button" disabled={pending !== null} onClick={() => runGate(version)}>
                        {pending === `gate-${version.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                        Run evaluation gate
                      </button>
                    ) : null}
                    {version.status === "approved" ? (
                      <button
                        className="actionButton"
                        type="button"
                        disabled={pending !== null || (template.is_platform_immutable && !isSuperAdmin) || (!template.is_platform_immutable && !widgetId)}
                        onClick={() => deploy(version)}
                      >
                        {pending === `deploy-${version.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                        Deploy
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
          {versions.length === 0 ? (
            <section className="statePanel" role="status">
              <h2>No versions yet</h2>
              <p>Create the first draft version above.</p>
            </section>
          ) : null}
        </div>
      </section>

      {canManage ? (
        <label>
          <span>Evaluation dataset id (for the gate button above)</span>
          <input type="text" value={datasetId} onChange={(event) => setDatasetId(event.target.value)} disabled={pending !== null} />
        </label>
      ) : null}

      <PromptAuditTrail session={session} entityId={template.id} />

      {message ? <p className="mutedText" role="status">{message}</p> : null}
      {error ? <p className="errorText" role="alert">{error}</p> : null}
    </section>
  );
}

function PromptAuditTrail({ session, entityId }: { session: DevelopmentDashboardSession; entityId: string }) {
  const [events, setEvents] = useState<Awaited<ReturnType<typeof listPromptAuditEvents>>["data"] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setPending(true);
    setError(null);
    try {
      const response = await listPromptAuditEvents(session);
      setEvents(response.data.filter((event) => event.entity_id === entityId));
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not load audit history.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="audit-trail-title">
      <p className="sectionKicker" id="audit-trail-title">Audit trail</p>
      <button className="smallButton" type="button" disabled={pending} onClick={load}>
        {pending ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
        Load audit history
      </button>
      {error ? <p className="errorText" role="alert">{error}</p> : null}
      {events ? (
        <div className="observabilityTraceList" role="list">
          {events.map((event) => (
            <div className="observabilityTraceRow" role="listitem" key={event.id}>
              <span className="badge">{event.action}</span>
              <span className="observabilityTraceRowChannel">{event.actor_user_id ?? "system"}</span>
              <span className="observabilityTraceRowTime">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(event.created_at))}</span>
            </div>
          ))}
          {events.length === 0 ? <p className="mutedText">No audit events recorded yet for this template.</p> : null}
        </div>
      ) : null}
    </section>
  );
}
