"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import type { EvaluationCandidate } from "../../lib/api/feedback-loop";
import { markCandidateDuplicate, promoteCandidate, updateCandidateTriage } from "../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const TRIAGE_STATUSES = ["new", "triaged", "needs_information", "accepted", "rejected", "duplicate", "resolved"];
const ROOT_CAUSE_CATEGORIES = [
  "answerable_factual", "unanswerable", "citation_required", "multi_document", "ambiguous", "fallback_expected",
  "prompt_injection", "system_prompt_extraction", "cross_assistant_leakage", "cross_workspace_leakage",
  "cross_organisation_leakage", "malicious_markdown_html", "malformed_input", "similar_but_absent",
  "irrelevant_off_topic", "long_input", "benign_edge_case",
];

type CandidateTriageFormProps = {
  session: DevelopmentDashboardSession;
  candidate: EvaluationCandidate;
  duplicateSuggestionIds: string[];
  canTriage: boolean;
};

export function CandidateTriageForm({ session, candidate, duplicateSuggestionIds, canTriage }: CandidateTriageFormProps) {
  const [current, setCurrent] = useState(candidate);
  const [triageStatus, setTriageStatus] = useState(candidate.triage_status);
  const [severity, setSeverity] = useState(candidate.severity);
  const [rootCause, setRootCause] = useState(candidate.root_cause_category ?? "");
  const [notes, setNotes] = useState(candidate.notes ?? "");
  const [datasetId, setDatasetId] = useState("");
  const [changelogNote, setChangelogNote] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function saveTriage() {
    setPending("save");
    setError(null);
    setMessage(null);
    try {
      const response = await updateCandidateTriage(session, current.id, {
        triage_status: triageStatus,
        severity,
        root_cause_category: rootCause || undefined,
        notes: notes || undefined,
      });
      setCurrent(response.data);
      setMessage("Triage saved.");
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not save triage.");
    } finally {
      setPending(null);
    }
  }

  async function promote() {
    if (!datasetId) {
      setError("Enter a dataset id to promote into.");
      return;
    }
    setPending("promote");
    setError(null);
    setMessage(null);
    try {
      const response = await promoteCandidate(session, current.id, datasetId, changelogNote || undefined);
      setCurrent(response.data.candidate);
      setMessage(`Promoted to case ${response.data.case_id} (dataset version ${response.data.dataset_version_event.to_version}).`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not promote candidate.");
    } finally {
      setPending(null);
    }
  }

  async function markDuplicateOf(targetId: string) {
    setPending(`duplicate-${targetId}`);
    setError(null);
    setMessage(null);
    try {
      const response = await markCandidateDuplicate(session, current.id, targetId);
      setCurrent(response.data);
      setTriageStatus(response.data.triage_status);
      setMessage(`Marked as a duplicate of ${targetId}.`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not mark as duplicate.");
    } finally {
      setPending(null);
    }
  }

  const isTerminal = ["rejected", "duplicate", "resolved"].includes(current.triage_status);

  return (
    <section className="reviewDecisionPanel" aria-labelledby="candidate-triage-title">
      <div className="reviewDecisionHeading">
        <div>
          <p className="sectionKicker">Triage</p>
          <h2 id="candidate-triage-title">What should happen next?</h2>
        </div>
        <span className={`badge answerState-${current.triage_status}`}>{current.triage_status.replace(/_/g, " ")}</span>
      </div>

      {isTerminal ? <p className="mutedText">This candidate has reached a terminal status ({current.triage_status}) and cannot be re-triaged.</p> : null}

      <label>
        <span>Triage status</span>
        <select value={triageStatus} onChange={(event) => setTriageStatus(event.target.value)} disabled={!canTriage || isTerminal}>
          {TRIAGE_STATUSES.map((status) => (
            <option key={status} value={status}>{status.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Severity</span>
        <select value={severity} onChange={(event) => setSeverity(event.target.value)} disabled={!canTriage || isTerminal}>
          {["low", "medium", "high", "critical"].map((level) => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Root cause category</span>
        <select value={rootCause} onChange={(event) => setRootCause(event.target.value)} disabled={!canTriage || isTerminal}>
          <option value="">Not yet classified</option>
          {ROOT_CAUSE_CATEGORIES.map((category) => (
            <option key={category} value={category}>{category.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Notes</span>
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} disabled={!canTriage || isTerminal} rows={3} />
      </label>

      {!canTriage ? <p className="mutedText">Viewers can inspect candidates but cannot triage them.</p> : null}

      <div className="reviewDecisionActions">
        <button className="actionButton" type="button" disabled={!canTriage || isTerminal || pending !== null} onClick={saveTriage}>
          {pending === "save" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
          Save triage
        </button>
      </div>

      {duplicateSuggestionIds.length > 0 && canTriage && !isTerminal ? (
        <div>
          <p className="sectionKicker">Potential duplicates</p>
          <div className="reviewDecisionActions">
            {duplicateSuggestionIds.map((id) => (
              <button key={id} className="smallButton" type="button" disabled={pending !== null} onClick={() => markDuplicateOf(id)}>
                Mark duplicate of {id.slice(0, 8)}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {current.triage_status === "accepted" ? (
        <div>
          <p className="sectionKicker">Promote to golden dataset</p>
          <label>
            <span>Target dataset id</span>
            <input type="text" value={datasetId} onChange={(event) => setDatasetId(event.target.value)} disabled={!canTriage || pending !== null} />
          </label>
          <label>
            <span>Changelog note</span>
            <input type="text" value={changelogNote} onChange={(event) => setChangelogNote(event.target.value)} disabled={!canTriage || pending !== null} />
          </label>
          <button className="actionButton" type="button" disabled={!canTriage || pending !== null || !!current.promoted_case_id} onClick={promote}>
            {pending === "promote" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : null}
            {current.promoted_case_id ? `Already promoted to case ${current.promoted_case_id.slice(0, 8)}` : "Promote"}
          </button>
        </div>
      ) : null}

      {message ? <p className="mutedText" role="status">{message}</p> : null}
      {error ? <p className="errorText" role="alert">{error}</p> : null}
    </section>
  );
}
