import Link from "next/link";

import type { DuplicateSuggestion, EvaluationCandidate } from "../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { CandidateTriageForm } from "./candidate-triage-form";

type CandidateDetailViewProps = {
  session: DevelopmentDashboardSession;
  candidate: EvaluationCandidate;
  potentialDuplicates: DuplicateSuggestion[];
  sourceTracePublicId: string | null;
  canTriage: boolean;
};

export function CandidateDetailView({ session, candidate, potentialDuplicates, sourceTracePublicId, canTriage }: CandidateDetailViewProps) {
  const backHref = `/feedback-loop?assistant=${candidate.widget_id}`;

  return (
    <section className="observabilityPage observabilityTraceDetail" aria-labelledby="candidate-detail-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Production candidate</p>
          <h1 id="candidate-detail-title">{candidate.redacted_question ?? "(no question captured)"}</h1>
          <p className="observabilitySubtitle">
            <span className={`badge answerState-${candidate.triage_status}`}>{candidate.triage_status.replace(/_/g, " ")}</span>{" "}
            · {candidate.signal_type.replace(/_/g, " ")} · severity {candidate.severity}
            {candidate.occurrence_count > 1 ? ` · seen ${candidate.occurrence_count} times` : ""}
            {candidate.is_reopen ? " · reopened" : ""}
          </p>
        </div>
        <Link className="smallButton" href={backHref}>Back to queue</Link>
      </header>

      {candidate.redacted_response ? (
        <section aria-label="Redacted production response">
          <p className="sectionKicker">Redacted production response</p>
          <p className="card observabilityRetrievalCardPreview">{candidate.redacted_response}</p>
        </section>
      ) : null}

      <div className="observabilityTraceDetailGrid">
        <section aria-label="Source">
          <p className="sectionKicker">Source</p>
          <ul className="observabilityGuardrailList">
            {sourceTracePublicId ? (
              <li>
                Trace: <Link href={`/observability/traces/${sourceTracePublicId}?assistant=${candidate.widget_id}`}>{sourceTracePublicId.slice(0, 8)}</Link>
              </li>
            ) : null}
            {candidate.source_conversation_id ? (
              <li>
                Conversation: <Link href={`/conversations/${candidate.source_conversation_id}?assistant=${candidate.widget_id}`}>{candidate.source_conversation_id.slice(0, 8)}</Link>
              </li>
            ) : null}
            {candidate.source_message_id ? (
              <li>
                Review item: <Link href={`/review/unanswered/${candidate.source_message_id}?assistant=${candidate.widget_id}`}>{candidate.source_message_id.slice(0, 8)}</Link>
              </li>
            ) : null}
            {!sourceTracePublicId && !candidate.source_conversation_id && !candidate.source_message_id ? (
              <li className="observabilityEmptyNote">No linked production source (manually created).</li>
            ) : null}
          </ul>

          <p className="sectionKicker">Evidence references</p>
          {candidate.evidence_refs_json && candidate.evidence_refs_json.length > 0 ? (
            <ul className="observabilityGuardrailList">
              {candidate.evidence_refs_json.map((ref, index) => (
                <li key={`${ref.document_id ?? "doc"}-${index}`}>{ref.source_title ?? ref.document_id ?? "Unknown source"}</li>
              ))}
            </ul>
          ) : (
            <p className="observabilityEmptyNote">No evidence references captured.</p>
          )}
        </section>

        <CandidateTriageForm
          session={session}
          candidate={candidate}
          duplicateSuggestionIds={potentialDuplicates.map((suggestion) => suggestion.candidate_id)}
          canTriage={canTriage}
        />
      </div>
    </section>
  );
}
