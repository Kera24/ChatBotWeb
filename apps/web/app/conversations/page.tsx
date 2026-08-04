import { ConversationsView } from "../../components/conversations/conversations-view";
import { NoAssistantSelectedState } from "../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listConversations } from "../../lib/api/conversations";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { getWidgetDetail } from "../../lib/api/widgets";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type ConversationsPageProps = {
  searchParams: Promise<{
    status?: string;
    channel?: string;
    started_after?: string;
    started_before?: string;
    limit?: string;
    offset?: string;
    assistant?: string;
  }>;
};

export default async function ConversationsPage({ searchParams }: ConversationsPageProps) {
  const params = await searchParams;
  const limit = clampNumber(params.limit, 20, 1, 50);
  const offset = clampNumber(params.offset, 0, 0, 10_000);
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const startedAfter = dateParam(params.started_after);
  const startedBefore = dateParam(params.started_before);

  const [result, assistantResult] = await Promise.all([
    loadConversationList(session, {
      assistantId: params.assistant,
      status: params.status,
      channel: params.channel,
      started_after: startedAfter,
      started_before: startedBefore,
      limit,
      offset,
    }),
    loadAssistant(session, params.assistant),
  ]);

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/conversations?assistant=${params.assistant}`} />;
  }
  if (!assistantResult.ok) {
    if (assistantResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(assistantResult.error)} retryHref={`/conversations?assistant=${params.assistant}`} />;
  }

  const conversations = result.data;
  const hasActiveFilters = Boolean(params.status || params.channel || startedAfter || startedBefore);

  return (
    <ConversationsView
      assistant={assistantResult.data}
      conversations={conversations}
      filters={{ status: params.status, channel: params.channel, startedAfter, startedBefore }}
      limit={limit}
      offset={offset}
      hasNext={conversations.length === limit}
      hasActiveFilters={hasActiveFilters}
    />
  );
}

function clampNumber(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

function dateParam(value: string | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  return value;
}

async function loadConversationList(
  session: DevelopmentDashboardSession,
  params: { assistantId: string; status?: string; channel?: string; started_after?: string; started_before?: string; limit: number; offset: number },
) {
  try {
    const response = await listConversations(session, params);
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
