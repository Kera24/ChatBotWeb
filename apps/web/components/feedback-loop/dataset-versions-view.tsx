import Link from "next/link";

import type { EvaluationDatasetVersionEvent } from "../../lib/api/feedback-loop";

type DatasetVersionsViewProps = {
  events: EvaluationDatasetVersionEvent[];
  assistantId: string;
};

export function DatasetVersionsView({ events, assistantId }: DatasetVersionsViewProps) {
  return (
    <section className="observabilityPage" aria-labelledby="dataset-versions-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Continuous Evaluation</p>
          <h1 id="dataset-versions-title">Dataset versions &amp; promotions</h1>
          <p className="observabilitySubtitle">Every golden-dataset version bump, with provenance back to the production candidate that caused it.</p>
        </div>
        <Link className="smallButton" href={`/feedback-loop?assistant=${assistantId}`}>Back to candidates</Link>
      </header>

      {events.length === 0 ? (
        <section className="statePanel" role="status">
          <h2>No dataset version events yet</h2>
          <p>Version events appear here once an accepted production candidate is promoted into a golden dataset.</p>
        </section>
      ) : (
        <div className="observabilityTraceList" role="list">
          {events.map((event) => (
            <div key={event.id} className="observabilityTraceRow" role="listitem">
              <span className="badge answerState-answered">v{event.from_version} → v{event.to_version}</span>
              <span>{event.changelog_note ?? "(no changelog note)"}</span>
              {event.candidate_id ? (
                <Link href={`/feedback-loop/candidates/${event.candidate_id}?assistant=${assistantId}`}>candidate {event.candidate_id.slice(0, 8)}</Link>
              ) : (
                <span className="observabilityEmptyNote">not candidate-sourced</span>
              )}
              <span className="observabilityTraceRowTime">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(event.created_at))}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
