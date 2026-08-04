import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { ReviewDecisionForm } from "./review-decision-form";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const item: ReviewItem = {
  conversation_id: "conversation-1",
  assistant_id: "assistant-1",
  assistant_message_id: "assistant-1",
  user_question: "What is the refund policy?",
  assistant_answer: "I do not have enough grounded context to answer.",
  answer_state: "fallback",
  error_code: null,
  channel: "dashboard_test",
  conversation_status: "active",
  model_key: "mock-default",
  provider_key: "mock",
  prompt_key: "grounded_rag_answer",
  prompt_version: 1,
  citation_count: 1,
  citations: [],
  created_at: "2026-07-12T00:00:00.000Z",
  estimated_cost: "0.00010000",
  latency_ms: 33,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

describe("ReviewDecisionForm", () => {
  it("disables update controls for viewers", () => {
    render(<ReviewDecisionForm session={{ ...session, role: "viewer" }} item={item} canUpdate={false} />);

    expect(screen.getByText("Viewers can inspect review items but cannot change review status.")).toBeTruthy();
    for (const button of screen.getAllByRole("button")) {
      expect(button.hasAttribute("disabled")).toBe(true);
    }
  });

  it("lets an admin submit a review status update with keyboard-accessible controls", async () => {
    const user = userEvent.setup();
    const updated = { ...item, review_status: "knowledge_gap", reviewer_note: "Add a refund article." };
    const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: updated }), { status: 200 }));
    vi.stubGlobal("fetch", mock);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
    render(<ReviewDecisionForm session={session} item={item} canUpdate />);

    await user.type(screen.getByLabelText("Reviewer note"), "Add a refund article.");
    await user.click(screen.getByRole("button", { name: "Mark knowledge gap" }));

    expect(mock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(mock.mock.calls[0][1].body))).toEqual({
      review_status: "knowledge_gap",
      reviewer_note: "Add a refund article.",
    });
    expect(await screen.findByText("Knowledge gap")).toBeTruthy();
  });

  it("maps API errors in the decision form", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "denied" }), { status: 403 })));
    render(<ReviewDecisionForm session={session} item={item} canUpdate />);

    await user.click(screen.getByRole("button", { name: "Mark reviewed" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("This development user does not have access to the selected workspace.")).toBeTruthy();
  });

  it("disables all buttons while a request is in flight", async () => {
    const user = userEvent.setup();
    let resolveFetch: (value: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveFetch = resolve; })));
    render(<ReviewDecisionForm session={session} item={item} canUpdate />);

    await user.click(screen.getByRole("button", { name: "Mark reviewed" }));
    expect(screen.getByText("Saving")).toBeTruthy();
    for (const button of screen.getAllByRole("button")) {
      expect(button.hasAttribute("disabled")).toBe(true);
    }

    resolveFetch(new Response(JSON.stringify({ success: true, data: { ...item, review_status: "reviewed" } }), { status: 200 }));
    expect(await screen.findByText("Reviewed")).toBeTruthy();
  });
});
