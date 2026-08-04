import { ConversationDetailView } from "../../../components/conversations/conversation-detail-view";
import { ConversationNotFoundState, ConversationWrongAssistantState, NoAssistantSelectedState } from "../../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";
import { getConversationDetail } from "../../../lib/api/conversations";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { getWidgetDetail } from "../../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

type ConversationDetailPageProps = {
  params: Promise<{ conversationId: string }>;
  searchParams: Promise<{ assistant?: string }>;
};

export default async function ConversationDetailPage({ params, searchParams }: ConversationDetailPageProps) {
  const { conversationId } = await params;
  const query = await searchParams;
  const session = await requireDashboardSession();
  if (!query.assistant) return <NoAssistantSelectedState />;

  const [result, assistantResult] = await Promise.all([
    loadConversationDetail(session, conversationId, query.assistant),
    loadAssistant(session, query.assistant),
  ]);

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    if (result.error.kind === "not_found") return <ConversationNotFoundState assistantId={query.assistant} />;
    return (
      <ErrorState
        message={messageForApiError(result.error)}
        retryHref={`/conversations/${conversationId}?assistant=${query.assistant}`}
      />
    );
  }
  if (!assistantResult.ok) {
    if (assistantResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(assistantResult.error)} retryHref={`/conversations/${conversationId}?assistant=${query.assistant}`} />;
  }

  const conversation = result.data;
  if (conversation.assistant_id && conversation.assistant_id !== query.assistant) {
    return <ConversationWrongAssistantState assistantId={query.assistant} />;
  }

  return <ConversationDetailView conversation={conversation} assistant={assistantResult.data} />;
}

async function loadConversationDetail(
  session: DevelopmentDashboardSession,
  conversationId: string,
  assistantId: string,
) {
  try {
    const response = await getConversationDetail(session, conversationId, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) {
      return { ok: false as const, error };
    }
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadAssistant(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const response = await getWidgetDetail(session, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
