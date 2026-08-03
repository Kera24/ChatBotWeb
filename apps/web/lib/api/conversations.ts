import { dashboardApiGet } from "./client";
import type {
  ConversationDetail,
  ConversationListMeta,
  ConversationListParams,
  ConversationSummary,
} from "./types";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export async function listConversations(
  session: DevelopmentDashboardSession,
  params: ConversationListParams = {},
) {
  return dashboardApiGet<ConversationSummary[], ConversationListMeta>({
    path: `/api/v1/workspaces/${session.workspaceId}/conversations`,
    session,
    searchParams: {
      organisation_id: session.organisationId,
      assistant_id: params.assistantId,
      status: params.status,
      channel: params.channel,
      started_after: params.started_after,
      started_before: params.started_before,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
    },
  });
}

export async function getConversationDetail(session: DevelopmentDashboardSession, conversationId: string, assistantId?: string) {
  return dashboardApiGet<ConversationDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/conversations/${conversationId}`,
    session,
    searchParams: { organisation_id: session.organisationId, ...(assistantId ? { assistant_id: assistantId } : {}) },
  });
}
