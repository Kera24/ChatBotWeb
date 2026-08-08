"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { createEvaluationCandidate } from "../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const SIGNAL_TYPES = [
  "thumbs_down", "fallback", "low_confidence", "grounding_failure", "missing_citation", "evidence_insufficient",
  "guardrail_trigger", "provider_failure", "high_latency", "support_report", "review_item", "manual_selection",
  "grader_advisory_failure",
];

type CandidateCreateFormProps = {
  session: DevelopmentDashboardSession;
  assistantId: string;
  sourceType?: string;
  sourceId?: string;
  prefillQuestion?: string;
  prefillResponse?: string;
};

export function CandidateCreateForm({ session, assistantId, sourceType, sourceId, prefillQuestion, prefillResponse }: CandidateCreateFormProps) {
  const router = useRouter();
  const [signalType, setSignalType] = useState(
    sourceType === "review_item" ? "review_item" : sourceType === "eval_result" ? "grader_advisory_failure" : "manual_selection",
  );
  const [severity, setSeverity] = useState("medium");
  const [question, setQuestion] = useState(prefillQuestion ?? "");
  const [response, setResponse] = useState(prefillResponse ?? "");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) {
      setError("A question is required.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const created = await createEvaluationCandidate(session, {
        widget_id: assistantId,
        signal_type: signalType,
        severity,
        question,
        response: response || null,
        notes: notes || null,
        source_trace_id: sourceType === "trace" ? sourceId : null,
        source_conversation_id: sourceType === "conversation" ? sourceId : null,
        source_message_id: sourceType === "review_item" ? sourceId : null,
      });
      router.push(`/feedback-loop/candidates/${created.data.id}?assistant=${assistantId}`);
    } catch (caught) {
      setError(isDashboardApiError(caught) ? messageForApiError(caught) : "Could not create the candidate.");
      setPending(false);
    }
  }

  return (
    <form className="reviewDecisionPanel" onSubmit={submit} aria-labelledby="create-candidate-title">
      <div className="reviewDecisionHeading">
        <div>
          <p className="sectionKicker">Continuous Evaluation</p>
          <h2 id="create-candidate-title">Create evaluation candidate</h2>
        </div>
      </div>
      {sourceType && sourceId ? <p className="mutedText">Linked to {sourceType.replace(/_/g, " ")} {sourceId.slice(0, 8)}.</p> : null}

      <label>
        <span>Signal type</span>
        <select value={signalType} onChange={(event) => setSignalType(event.target.value)}>
          {SIGNAL_TYPES.map((type) => (
            <option key={type} value={type}>{type.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Severity</span>
        <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
          {["low", "medium", "high", "critical"].map((level) => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Question (redacted automatically before storage)</span>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} />
      </label>
      <label>
        <span>Assistant response, if known</span>
        <textarea value={response} onChange={(event) => setResponse(event.target.value)} rows={3} />
      </label>
      <label>
        <span>Notes</span>
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} />
      </label>

      <div className="reviewDecisionActions">
        <button className="actionButton" type="submit" disabled={pending}>{pending ? "Creating..." : "Create candidate"}</button>
      </div>
      {error ? <p className="errorText" role="alert">{error}</p> : null}
    </form>
  );
}
