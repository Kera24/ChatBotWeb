import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ReviewQueueView } from "./review-queue-view";

function buildAssistant(overrides: Partial<WidgetDetail> = {}): WidgetDetail {
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
    ...overrides,
  };
}

const item: ReviewItem = {
  conversation_id: "conversation-1",
  assistant_id: "assistant-1",
  assistant_message_id: "assistant-message-1",
  user_question: "What is the refund policy?",
  assistant_answer: "Answer",
  answer_state: "fallback",
  error_code: null,
  channel: "widget",
  conversation_status: "active",
  model_key: null,
  provider_key: null,
  prompt_key: null,
  prompt_version: null,
  citation_count: 0,
  citations: [],
  created_at: "2026-07-12T00:00:00.000Z",
  estimated_cost: null,
  latency_ms: null,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

const metrics = { pending: 1, resolved: 0, needsKnowledge: 0, fallbacks: 1, lowConfidence: 0, failed: 0 };
const sample = { reviewedToday: 0, averageReviewAgeLabel: "No sample", sampleSize: 1 };

describe("ReviewQueueView", () => {
  it("renders the header, metrics, filters, list, and pagination when items are present", () => {
    render(
      <ReviewQueueView
        assistant={buildAssistant()}
        items={[item]}
        metrics={metrics}
        sample={sample}
        filters={{}}
        limit={20}
        offset={0}
        total={1}
        hasNext={false}
        hasActiveFilters={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Review Queue" })).toBeTruthy();
    expect(screen.getByLabelText("Review queue summary metrics")).toBeTruthy();
    expect(screen.getByLabelText("Review queue filters")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Knowledge gap review results" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Review queue pages" })).toBeTruthy();
  });

  it("shows the no-items empty state when there are no filters and no results", () => {
    render(
      <ReviewQueueView assistant={buildAssistant()} items={[]} metrics={metrics} sample={sample} filters={{}} limit={20} offset={0} total={0} hasNext={false} hasActiveFilters={false} />,
    );
    expect(screen.getByRole("heading", { name: "No flagged answers yet" })).toBeTruthy();
  });

  it("shows the no-filter-results empty state when filters are active but return nothing", () => {
    render(
      <ReviewQueueView
        assistant={buildAssistant()}
        items={[]}
        metrics={metrics}
        sample={sample}
        filters={{ reviewStatus: "dismissed" }}
        limit={20}
        offset={0}
        total={0}
        hasNext={false}
        hasActiveFilters
      />,
    );
    expect(screen.getByRole("heading", { name: "No review items match these filters" })).toBeTruthy();
  });

  it("shows an archived-assistant notice when the assistant is archived", () => {
    render(
      <ReviewQueueView
        assistant={buildAssistant({ operational_status: "archived" })}
        items={[item]}
        metrics={metrics}
        sample={sample}
        filters={{}}
        limit={20}
        offset={0}
        total={1}
        hasNext={false}
        hasActiveFilters={false}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
