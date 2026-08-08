import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { EvaluationCandidate } from "../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { CandidateTriageForm } from "./candidate-triage-form";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

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

describe("CandidateTriageForm", () => {
  it("disables controls for viewers", () => {
    render(<CandidateTriageForm session={session} candidate={buildCandidate()} duplicateSuggestionIds={[]} canTriage={false} />);
    expect(screen.getByText("Viewers can inspect candidates but cannot triage them.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Save triage/ }).hasAttribute("disabled")).toBe(true);
  });

  it("saves a triage status update via PATCH", async () => {
    const user = userEvent.setup();
    const updated = buildCandidate({ triage_status: "triaged", first_triaged_at: "2026-07-12T01:00:00.000Z" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: updated }), { status: 200 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<CandidateTriageForm session={session} candidate={buildCandidate()} duplicateSuggestionIds={[]} canTriage />);

    await user.selectOptions(screen.getByLabelText("Triage status"), "triaged");
    await user.click(screen.getByRole("button", { name: /Save triage/ }));

    expect(await screen.findByText("Triage saved.")).toBeTruthy();
  });

  it("shows a promote action only once a candidate is accepted", () => {
    render(<CandidateTriageForm session={session} candidate={buildCandidate({ triage_status: "accepted" })} duplicateSuggestionIds={[]} canTriage />);
    expect(screen.getByRole("button", { name: /Promote/ })).toBeTruthy();
  });

  it("does not show a promote action for a new candidate", () => {
    render(<CandidateTriageForm session={session} candidate={buildCandidate({ triage_status: "new" })} duplicateSuggestionIds={[]} canTriage />);
    expect(screen.queryByRole("button", { name: /Promote/ })).toBeNull();
  });

  it("surfaces potential duplicate suggestions with mark-duplicate actions", () => {
    render(
      <CandidateTriageForm session={session} candidate={buildCandidate()} duplicateSuggestionIds={["candidate-2"]} canTriage />,
    );
    expect(screen.getByRole("button", { name: /Mark duplicate of candidat/ })).toBeTruthy();
  });

  it("prevents re-triaging a terminal candidate", () => {
    render(<CandidateTriageForm session={session} candidate={buildCandidate({ triage_status: "resolved" })} duplicateSuggestionIds={[]} canTriage />);
    expect(screen.getByText(/terminal status/)).toBeTruthy();
    expect(screen.getByLabelText("Triage status").hasAttribute("disabled")).toBe(true);
  });
});
