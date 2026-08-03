import { dashboardApiGet, dashboardApiPatch } from "./client";
import type { ReviewItem, ReviewItemDetail, ReviewListMeta, ReviewListParams } from "./types";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export async function listUnansweredReviewItems(
  session: DevelopmentDashboardSession,
  params: ReviewListParams = {},
) {
  return dashboardApiGet<ReviewItem[], ReviewListMeta>({
    path: `/api/v1/workspaces/${session.workspaceId}/review/unanswered`,
    session,
    searchParams: {
      organisation_id: session.organisationId,
      assistant_id: params.assistantId,
      answer_state: params.answer_state,
      review_status: params.review_status,
      channel: params.channel,
      created_after: params.created_after,
      created_before: params.created_before,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
    },
  });
}

export async function getUnansweredReviewItem(session: DevelopmentDashboardSession, assistantMessageId: string, assistantId: string) {
  return dashboardApiGet<ReviewItemDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/review/unanswered/${assistantMessageId}`,
    session,
    searchParams: { organisation_id: session.organisationId, assistant_id: assistantId },
  });
}

export async function updateUnansweredReviewStatus(
  session: DevelopmentDashboardSession,
  assistantMessageId: string,
  assistantIdOrPayload: string | { review_status: string; reviewer_note?: string | null },
  maybePayload?: { review_status: string; reviewer_note?: string | null },
) {
  const assistantId = typeof assistantIdOrPayload === "string" ? assistantIdOrPayload : undefined;
  const payload = typeof assistantIdOrPayload === "string" ? maybePayload : assistantIdOrPayload;
  return dashboardApiPatch<ReviewItem>({
    path: `/api/v1/workspaces/${session.workspaceId}/review/unanswered/${assistantMessageId}`,
    session,
    searchParams: { organisation_id: session.organisationId, ...(assistantId ? { assistant_id: assistantId } : {}) },
    body: payload,
  });
}
