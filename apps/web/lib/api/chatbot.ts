import { dashboardApiPost } from "./client";
import type { RAGAnswerResponse } from "./types";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type ChatbotAnswerRequest = {
  query: string;
  conversationId?: string | null;
  assistantId: string;
};

export function answerChatbotQuestion(session: DevelopmentDashboardSession, request: ChatbotAnswerRequest) {
  return dashboardApiPost<RAGAnswerResponse>({
    path: `/api/v1/workspaces/${session.workspaceId}/rag/answer`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body: {
      query: request.query,
      assistant_id: request.assistantId,
      ...(request.conversationId ? { conversation_id: request.conversationId } : {}),
    },
  });
}
