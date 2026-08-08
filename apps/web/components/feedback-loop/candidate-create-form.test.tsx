import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { render, screen, userEvent } from "../../test/test-utils";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { CandidateCreateForm } from "./candidate-create-form";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

describe("CandidateCreateForm", () => {
  it("requires a question before submitting", async () => {
    const user = userEvent.setup();
    const mock = vi.fn();
    vi.stubGlobal("fetch", mock);
    render(<CandidateCreateForm session={session} assistantId="assistant-1" />);

    await user.click(screen.getByRole("button", { name: /Create candidate/ }));

    expect(await screen.findByText("A question is required.")).toBeTruthy();
    expect(mock).not.toHaveBeenCalled();
  });

  it("submits the redacted question with the resolved source ids", async () => {
    const user = userEvent.setup();
    const mock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: { id: "candidate-9" } }), { status: 201 }),
    );
    vi.stubGlobal("fetch", mock);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<CandidateCreateForm session={session} assistantId="assistant-1" sourceType="trace" sourceId="trace-1" />);
    await user.type(screen.getByLabelText(/Question/), "How do I export my data?");
    await user.click(screen.getByRole("button", { name: /Create candidate/ }));

    expect(mock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String(mock.mock.calls[0][1].body));
    expect(body.question).toBe("How do I export my data?");
    expect(body.source_trace_id).toBe("trace-1");
    expect(body.source_conversation_id).toBeNull();
    expect(body.widget_id).toBe("assistant-1");
  });

  it("defaults the signal type to review_item when linked from a review item", () => {
    render(<CandidateCreateForm session={session} assistantId="assistant-1" sourceType="review_item" sourceId="message-1" />);
    expect(screen.getByLabelText("Signal type")).toHaveValue("review_item");
  });

  it("prefills question/response text when provided", () => {
    render(
      <CandidateCreateForm
        session={session}
        assistantId="assistant-1"
        sourceType="eval_result"
        prefillQuestion="What is the refund window?"
        prefillResponse="I don't know."
      />,
    );
    expect(screen.getByLabelText(/Question/)).toHaveValue("What is the refund window?");
    expect(screen.getByLabelText(/Assistant response/)).toHaveValue("I don't know.");
    expect(screen.getByLabelText("Signal type")).toHaveValue("grader_advisory_failure");
  });
});
