import { getConversationDetail, listConversations } from "./conversations";
import { listDocuments, type DocumentRecord } from "./documents";
import { listUnansweredReviewItems } from "./review";
import type { ConversationDetail, ConversationSummary, ReviewItem } from "./types";
import { listWidgets, type WidgetSummary } from "./widgets";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type AnalyticsFilters = {
  assistantId?: string;
  started_after?: string;
  started_before?: string;
  conversation_status?: string;
  conversation_channel?: string;
  document_status?: string;
};

export type AnalyticsData = {
  filters: AnalyticsFilters;
  documents: DocumentRecord[];
  conversations: ConversationSummary[];
  conversationDetails: ConversationDetail[];
  widgets: WidgetSummary[];
  reviewItems: ReviewItem[];
  reviewTotal: number;
  recentWindowLimit: number;
  detailSampleLimit: number;
};

const RECENT_WINDOW_LIMIT = 100;
const DETAIL_SAMPLE_LIMIT = 25;

export async function loadAnalyticsData(session: DevelopmentDashboardSession, filters: AnalyticsFilters = {}): Promise<AnalyticsData> {
  const [documents, conversations, widgets, reviewItems] = await Promise.all([
    listDocuments(session, filters.assistantId),
    listConversations(session, {
      assistantId: filters.assistantId,
      status: filters.conversation_status,
      channel: filters.conversation_channel,
      started_after: filters.started_after,
      started_before: filters.started_before,
      limit: RECENT_WINDOW_LIMIT,
      offset: 0,
    }),
    listWidgets(session),
    listUnansweredReviewItems(session, {
      assistantId: filters.assistantId,
      review_status: "open",
      channel: filters.conversation_channel,
      created_after: filters.started_after,
      created_before: filters.started_before,
      limit: RECENT_WINDOW_LIMIT,
      offset: 0,
    }),
  ]);

  const filteredDocuments = filters.document_status
    ? documents.data.filter((document) => document.status === filters.document_status)
    : documents.data;
  const detailTargets = conversations.data.slice(0, DETAIL_SAMPLE_LIMIT);
  const details = await Promise.all(detailTargets.map((conversation) => filters.assistantId ? getConversationDetail(session, conversation.id, filters.assistantId) : getConversationDetail(session, conversation.id)));

  return {
    filters,
    documents: filteredDocuments,
    conversations: conversations.data,
    conversationDetails: details.map((detail) => detail.data),
    widgets: widgets.data,
    reviewItems: reviewItems.data,
    reviewTotal: reviewItems.meta?.total ?? reviewItems.data.length,
    recentWindowLimit: RECENT_WINDOW_LIMIT,
    detailSampleLimit: DETAIL_SAMPLE_LIMIT,
  };
}
