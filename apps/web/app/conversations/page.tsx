import Link from "next/link";

import { ConversationFilters } from "../../components/conversations/conversation-filters";
import { ConversationList } from "../../components/conversations/conversation-list";
import { PaginationControls } from "../../components/conversations/pagination-controls";
import {
  AccessDeniedState,
  EmptyState,
  ErrorState,
} from "../../components/conversations/state-panels";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listConversations } from "../../lib/api/conversations";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type ConversationsPageProps = {
  searchParams: Promise<{
    status?: string;
    channel?: string;
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
  if (!params.assistant) return <ErrorState message="Select an assistant before viewing conversations." retryHref="/dashboard" />;

  const result = await loadConversationList(session, {
    assistantId: params.assistant,
    status: params.status,
    channel: params.channel,
    limit,
    offset,
  });

  if (!result.ok) {
    if (result.error.kind === "forbidden") {
      return <AccessDeniedState />;
    }
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/conversations?assistant=${params.assistant}`} />;
  }

  const conversations = result.data;

  return (
    <section className="conversationPage" aria-labelledby="conversation-title">
      <div className="conversationHero">
        <div>
          <p className="eyebrow">Conversation history</p>
          <h2 id="conversation-title">The human record of answers</h2>
          <p>Review tenant-scoped chats, fallback moments, and source-grounded answers without exposing public widget behaviour.</p>
        </div>
        <div className="conversationHeroAside">
          <strong>{conversations.length}</strong>
          <span>visible on this page</span>
        </div>
      </div>

      <div className="conversationToolbar">
        <ConversationFilters status={params.status} channel={params.channel} limit={limit} assistantId={params.assistant} />
        <Link className="actionButton" href={`/conversations?assistant=${params.assistant}`} aria-label="Refresh conversation history">Refresh</Link>
      </div>

      {conversations.length === 0 ? <EmptyState /> : <ConversationList conversations={conversations} assistantId={params.assistant} />}

      <PaginationControls
        basePath="/conversations"
        status={params.status}
        channel={params.channel}
        limit={limit}
        offset={offset}
        hasNext={conversations.length === limit}
        assistantId={params.assistant}
      />
    </section>
  );
}

function clampNumber(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}


async function loadConversationList(
  session: DevelopmentDashboardSession,
  params: { assistantId: string; status?: string; channel?: string; limit: number; offset: number },
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
