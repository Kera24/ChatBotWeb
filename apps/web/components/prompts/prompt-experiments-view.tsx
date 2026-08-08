"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import {
  type ArmMetrics,
  type PromptExperiment,
  type PromptLayer,
  type PromptVersion,
  completePromptExperiment,
  createPromptExperiment,
  getPromptExperimentMetrics,
  killPromptExperiment,
  listPromptExperiments,
  startPromptExperiment,
} from "../../lib/api/prompts";
import type { WidgetSummary } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type PromptExperimentsViewProps = {
  session: DevelopmentDashboardSession;
  templateId: string;
  layer: PromptLayer;
  versions: PromptVersion[];
  widgets: WidgetSummary[];
  canManage: boolean;
  isSuperAdmin: boolean;
};

export function PromptExperimentsView({ session, layer, versions, widgets, canManage, isSuperAdmin }: PromptExperimentsViewProps) {
  const [widgetId, setWidgetId] = useState(widgets[0]?.id ?? "");
  const [experiments, setExperiments] = useState<PromptExperiment[]>([]);
  const [controlVersionId, setControlVersionId] = useState(versions[0]?.id ?? "");
  const [candidateVersionId, setCandidateVersionId] = useState(versions[1]?.id ?? versions[0]?.id ?? "");
  const [traffic, setTraffic] = useState(10);
  const [datasetId, setDatasetId] = useState("");
  const [maxDurationHours, setMaxDurationHours] = useState<number | "">("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [metricsByExperiment, setMetricsByExperiment] = useState<Record<string, ArmMetrics[]>>({});

  function resetStatus() {
    setError(null);
    setMessage(null);
  }

  async function loadExperiments() {
    if (!widgetId) {
      setError("Select an assistant first.");
      return;
    }
    setPending("load");
    resetStatus();
    try {
      const response = await listPromptExperiments(session, widgetId);
      setExperiments(response.data);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not load experiments.");
    } finally {
      setPending(null);
    }
  }

  async function create() {
    if (!widgetId || !controlVersionId || !candidateVersionId) {
      setError("Select an assistant, a control version, and a candidate version.");
      return;
    }
    setPending("create");
    resetStatus();
    try {
      const response = await createPromptExperiment(session, {
        widget_id: widgetId,
        layer,
        control_version_id: controlVersionId,
        candidate_version_id: candidateVersionId,
        traffic_allocation_percentage: traffic,
        evaluation_dataset_id: datasetId || undefined,
        max_duration_hours: maxDurationHours === "" ? undefined : maxDurationHours,
      });
      setExperiments((current) => [response.data, ...current]);
      setMessage("Experiment created in draft status. It requires a passed evaluation gate before it can start.");
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not create experiment.");
    } finally {
      setPending(null);
    }
  }

  async function start(experiment: PromptExperiment) {
    setPending(`start-${experiment.id}`);
    resetStatus();
    try {
      const response = await startPromptExperiment(session, experiment.id);
      setExperiments((current) => current.map((item) => (item.id === experiment.id ? response.data : item)));
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not start experiment - it likely has not passed the evaluation gate yet.");
    } finally {
      setPending(null);
    }
  }

  async function kill(experiment: PromptExperiment) {
    setPending(`kill-${experiment.id}`);
    resetStatus();
    try {
      const response = await killPromptExperiment(session, experiment.id);
      setExperiments((current) => current.map((item) => (item.id === experiment.id ? response.data : item)));
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not kill experiment.");
    } finally {
      setPending(null);
    }
  }

  async function complete(experiment: PromptExperiment) {
    setPending(`complete-${experiment.id}`);
    resetStatus();
    try {
      const response = await completePromptExperiment(session, experiment.id);
      setExperiments((current) => current.map((item) => (item.id === experiment.id ? response.data : item)));
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not complete experiment.");
    } finally {
      setPending(null);
    }
  }

  async function loadMetrics(experiment: PromptExperiment) {
    setPending(`metrics-${experiment.id}`);
    resetStatus();
    try {
      const response = await getPromptExperimentMetrics(session, experiment.id);
      setMetricsByExperiment((current) => ({ ...current, [experiment.id]: response.data.arms }));
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not load experiment metrics.");
    } finally {
      setPending(null);
    }
  }

  const isPlatformLayer = layer === "platform_core";
  const canCreate = canManage && (!isPlatformLayer || isSuperAdmin);

  return (
    <section className="observabilityPage" aria-labelledby="prompt-experiments-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Prompt Experiments</p>
          <h1 id="prompt-experiments-title">Controlled A/B experiments</h1>
          <p className="observabilitySubtitle">
            Deterministic traffic split by conversation, kill switch, maximum duration, and directional (non-statistical) per-arm metrics -
            see docs/architecture/prompts.md for the exact scope cuts.
          </p>
        </div>
      </header>

      {widgets.length ? (
        <label>
          <span>Assistant</span>
          <select value={widgetId} onChange={(event) => setWidgetId(event.target.value)} disabled={pending !== null}>
            <option value="">Select an assistant</option>
            {widgets.map((widget) => (
              <option key={widget.id} value={widget.id}>{widget.display_name}</option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="reviewDecisionActions">
        <button className="smallButton" type="button" disabled={pending !== null} onClick={loadExperiments}>
          {pending === "load" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
          Load experiments for this assistant
        </button>
      </div>

      {canCreate ? (
        <section className="reviewDecisionPanel" aria-labelledby="new-experiment-title">
          <div className="reviewDecisionHeading">
            <div>
              <p className="sectionKicker">New experiment</p>
              <h2 id="new-experiment-title">Set up a control vs. candidate test</h2>
            </div>
          </div>
          <label>
            <span>Control version</span>
            <select value={controlVersionId} onChange={(event) => setControlVersionId(event.target.value)} disabled={pending !== null}>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>v{version.version_number} ({version.status})</option>
              ))}
            </select>
          </label>
          <label>
            <span>Candidate version</span>
            <select value={candidateVersionId} onChange={(event) => setCandidateVersionId(event.target.value)} disabled={pending !== null}>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>v{version.version_number} ({version.status})</option>
              ))}
            </select>
          </label>
          <label>
            <span>Candidate traffic allocation (%)</span>
            <input type="number" min={0} max={100} value={traffic} onChange={(event) => setTraffic(Number(event.target.value))} disabled={pending !== null} />
          </label>
          <label>
            <span>Evaluation dataset id (required before it can start)</span>
            <input type="text" value={datasetId} onChange={(event) => setDatasetId(event.target.value)} disabled={pending !== null} />
          </label>
          <label>
            <span>Maximum duration (hours, optional)</span>
            <input type="number" min={1} value={maxDurationHours} onChange={(event) => setMaxDurationHours(event.target.value === "" ? "" : Number(event.target.value))} disabled={pending !== null} />
          </label>
          {isPlatformLayer ? <p className="mutedText">This is the platform-immutable layer - experiments here require super admin and a passed safety gate before they can start.</p> : null}
          <div className="reviewDecisionActions">
            <button className="actionButton" type="button" disabled={pending !== null} onClick={create}>
              {pending === "create" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
              Create experiment
            </button>
          </div>
        </section>
      ) : null}

      <div className="observabilityTraceList" role="list">
        {experiments.map((experiment) => {
          const metrics = metricsByExperiment[experiment.id];
          return (
            <div className="card" role="listitem" key={experiment.id}>
              <div className="reviewDecisionHeading">
                <div>
                  <p>
                    <span className={`badge answerState-${experiment.status}`}>{experiment.status}</span>{" "}
                    <span className={`badge severity-${experiment.safety_gate_state === "passed" ? "low" : "high"}`}>gate: {experiment.safety_gate_state}</span>
                  </p>
                  <p className="mutedText">{experiment.traffic_allocation_percentage}% candidate traffic</p>
                </div>
              </div>
              {canManage ? (
                <div className="reviewDecisionActions">
                  {experiment.status === "draft" ? (
                    <button className="smallButton" type="button" disabled={pending !== null} onClick={() => start(experiment)}>
                      {pending === `start-${experiment.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                      Start
                    </button>
                  ) : null}
                  {experiment.status === "running" ? (
                    <button className="smallButton" type="button" disabled={pending !== null} onClick={() => kill(experiment)}>
                      {pending === `kill-${experiment.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                      Kill switch
                    </button>
                  ) : null}
                  {experiment.status === "running" ? (
                    <button className="smallButton" type="button" disabled={pending !== null} onClick={() => complete(experiment)}>
                      Complete
                    </button>
                  ) : null}
                  <button className="smallButton" type="button" disabled={pending !== null} onClick={() => loadMetrics(experiment)}>
                    {pending === `metrics-${experiment.id}` ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
                    Load metrics
                  </button>
                </div>
              ) : null}
              {metrics ? (
                <div>
                  <p className="mutedText">Directional metrics only - not statistically significant.</p>
                  {metrics.map((arm) => (
                    <p key={arm.arm} className="mutedText">
                      {arm.arm}: {arm.request_count} requests, fallback rate {arm.fallback_rate === null ? "n/a" : `${(arm.fallback_rate * 100).toFixed(1)}%`}
                      {arm.sufficient_sample ? "" : " (sample too small to be meaningful)"}
                    </p>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
        {experiments.length === 0 ? <p className="mutedText">No experiments loaded yet.</p> : null}
      </div>

      {message ? <p className="mutedText" role="status">{message}</p> : null}
      {error ? <p className="errorText" role="alert">{error}</p> : null}
    </section>
  );
}
