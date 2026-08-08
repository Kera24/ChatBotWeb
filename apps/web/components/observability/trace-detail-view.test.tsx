import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { AITraceDetail } from "../../lib/api/observability";
import { TraceDetailView } from "./trace-detail-view";

const trace: AITraceDetail = {
  summary: {
    trace_id: "trace-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    assistant_id: "assistant-1",
    conversation_id: "conversation-1",
    channel: "widget",
    status: "completed",
    answer_state: "answered",
    fallback_used: false,
    total_latency_ms: 120,
    provider_key: "mock",
    model_key: "mock-default",
    total_tokens: 20,
    estimated_cost: null,
    cost_currency: "USD",
    eval_run_id: null,
    eval_case_id: null,
    created_at: "2026-07-12T00:00:00.000Z",
  },
  stages: [],
  retrieval: [],
  model_calls: [],
  guardrails: [],
};

describe("TraceDetailView", () => {
  it("links to create an evaluation candidate from this trace", () => {
    render(<TraceDetailView trace={trace} assistantId="assistant-1" includeContent={false} />);

    const link = screen.getByRole("link", { name: /Create evaluation candidate/ });
    expect(link.getAttribute("href")).toBe("/feedback-loop/candidates/new?source_type=trace&source_id=trace-1&assistant=assistant-1");
  });

  it("does not render the candidate link without an assistant id", () => {
    render(<TraceDetailView trace={trace} includeContent={false} />);
    expect(screen.queryByRole("link", { name: /Create evaluation candidate/ })).toBeNull();
  });
});
