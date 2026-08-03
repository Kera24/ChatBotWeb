import { listConversations } from "./conversations";
import { listDocuments, type DocumentRecord } from "./documents";
import { listUnansweredReviewItems } from "./review";
import type { ConversationSummary, ReviewItem } from "./types";
import { listWidgets, type WidgetSummary } from "./widgets";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type OverviewData = {
  documents: DocumentRecord[];
  conversations: ConversationSummary[];
  widgets: WidgetSummary[];
  reviewItems: ReviewItem[];
  reviewTotal: number;
};

export async function loadOverviewData(session: DevelopmentDashboardSession): Promise<OverviewData> {
  const widgets = await listWidgets(session);
  const assistants = widgets.data;

  if (assistants.length === 0) {
    const [documents, conversations, reviewItems] = await Promise.all([
      listDocuments(session),
      listConversations(session, { limit: 50, offset: 0 }),
      listUnansweredReviewItems(session, { review_status: "open", limit: 20, offset: 0 }),
    ]);
    return {
      documents: documents.data,
      conversations: conversations.data,
      widgets: widgets.data,
      reviewItems: reviewItems.data,
      reviewTotal: reviewItems.meta?.total ?? reviewItems.data.length,
    };
  }

  const scoped = await Promise.all(assistants.map(async (assistant) => {
    const [documents, conversations, reviewItems] = await Promise.all([
      listDocuments(session, assistant.id),
      listConversations(session, { assistantId: assistant.id, limit: 50, offset: 0 }),
      listUnansweredReviewItems(session, { assistantId: assistant.id, review_status: "open", limit: 20, offset: 0 }),
    ]);
    return { documents, conversations, reviewItems };
  }));

  return {
    documents: scoped.flatMap((item) => item.documents.data),
    conversations: scoped.flatMap((item) => item.conversations.data),
    widgets: widgets.data,
    reviewItems: scoped.flatMap((item) => item.reviewItems.data),
    reviewTotal: scoped.reduce((total, item) => total + (item.reviewItems.meta?.total ?? item.reviewItems.data.length), 0),
  };
}
