import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { EvaluationCandidate, FeedbackLoopMetrics } from "../../lib/api/feedback-loop";
import type { WidgetDetail } from "../../lib/api/widgets";
import { FeedbackLoopDashboard } from "./feedback-loop-dashboard";

function buildAssistant(): WidgetDetail {
  return {
    id: "assistant-1",
    display_name: "Admissions Assistant",
    public_identifier: "public-1",
    public_credential_id: "credential-1",
    publication_status: "published",
    active_revision_number: 2,
    active_published_revision_id: "revision-2",
    draft_revision_id: "revision-3",
    draft_dirty: false,
    operational_status: "enabled",
    pilot_status: "approved",
    release_channel: "staging",
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-10T00:00:00.000Z",
    draft: null,
    active_published_revision: null,
    diff: null,
  };
}

function buildCandidate(overrides: Partial<EvaluationCandidate> = {}): EvaluationCandidate {
  return {
    id: "candidate-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    widget_id: "assistant-1",
    source_trace_id: null,
    source_conversation_id: null,
    source_message_id: null,
    signal_type: "fallback",
    severity: "medium",
    redacted_question: "How do I cancel my subscription?",
    redacted_response: null,
    redaction_version: "v1",
    evidence_refs_json: null,
    expected_behaviour_note: null,
    triage_status: "new",
    root_cause_category: null,
    expected_document_ids_json: null,
    expected_source_labels_json: null,
    expected_answerability: null,
    triage_details_json: null,
    reviewer_id: null,
    notes: null,
    dedup_hash: "hash-1",
    duplicate_of_id: null,
    occurrence_count: 1,
    is_reopen: false,
    dataset_destination_id: null,
    promoted_case_id: null,
    first_triaged_at: null,
    resolved_at: null,
    created_at: "2026-07-12T00:00:00.000Z",
    updated_at: "2026-07-12T00:00:00.000Z",
    ...overrides,
  };
}

const metrics: FeedbackLoopMetrics = {
  candidates_by_status: { new: 3, triaged: 1, accepted: 1, resolved: 2 },
  candidates_by_signal_type: { fallback: 5 },
  candidates_by_severity: { low: 2, medium: 3 },
  failures_by_root_cause: {},
  avg_time_to_triage_hours: 4.5,
  avg_time_to_resolution_hours: 20,
  cases_added_per_dataset_version: {},
  recurrence_rate: 0.4,
  reopen_rate: 0.1,
  regression_escape_rate: 0.0,
  fixed_case_confirmation_rate: 1.0,
};

describe("FeedbackLoopDashboard", () => {
  it("renders metric tiles and the candidate queue", () => {
    render(
      <FeedbackLoopDashboard
        assistant={buildAssistant()}
        candidates={[buildCandidate()]}
        metrics={metrics}
        filters={{}}
        total={1}
      />,
    );

    expect(screen.getByRole("heading", { name: "Admissions Assistant" })).toBeTruthy();
    expect(screen.getByText("40.0%")).toBeTruthy();
    expect(screen.getByText("How do I cancel my subscription?")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Dataset versions" }).getAttribute("href")).toBe("/feedback-loop/versions?assistant=assistant-1");
  });

  it("shows an empty state when there are no matching candidates", () => {
    render(<FeedbackLoopDashboard assistant={buildAssistant()} candidates={[]} metrics={metrics} filters={{}} total={0} />);
    expect(screen.getByText("No production candidates match these filters")).toBeTruthy();
  });
});
