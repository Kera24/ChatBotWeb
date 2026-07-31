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
  const [documents, conversations, widgets, reviewItems] = await Promise.all([
    listDocuments(session),
    listConversations(session, { limit: 50, offset: 0 }),
    listWidgets(session),
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
