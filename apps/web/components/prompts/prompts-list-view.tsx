"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { CUSTOMER_EDITABLE_LAYERS, createPromptTemplate, type PromptLayer, type PromptTemplate } from "../../lib/api/prompts";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type PromptsListViewProps = {
  session: DevelopmentDashboardSession;
  templates: PromptTemplate[];
  canManage: boolean;
};

function formatLayer(layer: string): string {
  return layer.replace(/_/g, " ");
}

export function PromptsListView({ session, templates: initialTemplates, canManage }: PromptsListViewProps) {
  const [templates, setTemplates] = useState(initialTemplates);
  const [layer, setLayer] = useState<PromptLayer>(CUSTOMER_EDITABLE_LAYERS[0]);
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createTemplate() {
    if (!name.trim()) {
      setError("Enter a name for the new prompt template.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const response = await createPromptTemplate(session, layer, name.trim());
      setTemplates((current) => [...current, response.data]);
      setName("");
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not create prompt template.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="observabilityPage" aria-labelledby="prompts-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Prompt Management</p>
          <h1 id="prompts-title">Prompts</h1>
          <p className="observabilitySubtitle">
            Versioned prompt layers: draft, evaluate, approve, deploy, run controlled experiments, and roll back - see the platform safety policy
            plus each workspace&apos;s persona and organisation guidance.
          </p>
        </div>
      </header>

      <div className="observabilityTraceList" role="list">
        {templates.map((template) => (
          <Link className="observabilityTraceRow" role="listitem" href={`/prompts/${template.id}`} key={template.id}>
            <span className={`badge ${template.is_platform_immutable ? "severity-critical" : "severity-low"}`}>{formatLayer(template.layer)}</span>
            <span className="observabilityTraceRowChannel">{template.name}</span>
            {template.is_platform_immutable ? <span className="mutedText">Platform-immutable</span> : <span className="mutedText">Workspace-editable</span>}
          </Link>
        ))}
        {templates.length === 0 ? (
          <section className="statePanel" role="status">
            <h2>No prompt templates yet</h2>
            <p>The platform core policy template is created automatically the first time this page loads.</p>
          </section>
        ) : null}
      </div>

      {canManage ? (
        <section className="reviewDecisionPanel" aria-labelledby="create-template-title">
          <div className="reviewDecisionHeading">
            <div>
              <p className="sectionKicker">New template</p>
              <h2 id="create-template-title">Add a customer-editable layer</h2>
            </div>
          </div>
          <p className="mutedText">Only the assistant persona/tone and organisation guidance layers can be created here - the platform core policy is managed by super admins.</p>
          <label>
            <span>Layer</span>
            <select value={layer} onChange={(event) => setLayer(event.target.value as PromptLayer)} disabled={pending}>
              {CUSTOMER_EDITABLE_LAYERS.map((option) => (
                <option key={option} value={option}>{formatLayer(option)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Name</span>
            <input type="text" value={name} onChange={(event) => setName(event.target.value)} disabled={pending} placeholder="e.g. Support Bot Persona" />
          </label>
          <div className="reviewDecisionActions">
            <button className="actionButton" type="button" disabled={pending} onClick={createTemplate}>
              {pending ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
              Create template
            </button>
          </div>
          {error ? <p className="errorText" role="alert">{error}</p> : null}
        </section>
      ) : null}
    </section>
  );
}
