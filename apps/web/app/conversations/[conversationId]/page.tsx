import Link from "next/link";

import { ConversationStatusBadge } from "../../../components/conversations/conversation-status-badge";
import { formatDate, formatEnum } from "../../../components/conversations/conversation-list";
import { MessageThread } from "../../../components/conversations/message-thread";
import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../../components/conversations/state-panels";
import { getConversationDetail } from "../../../lib/api/conversations";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../../lib/auth/development-session";

export const dynamic = "force-dynamic";

type ConversationDetailPageProps = {
  params: Promise<{ conversationId: string }>;
};

export default async function ConversationDetailPage({ params }: ConversationDetailPageProps) {
  const { conversationId } = await params;
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadConversationDetail(tenant.session, conversationId);

  if (!result.ok) {
    if (result.error.kind === "forbidden") {
      return <AccessDeniedState />;
    }
    return (
      <ErrorState
        message={messageForApiError(result.error)}
        retryHref={`/conversations/${conversationId}`}
      />
    );
  }

  const conversation = result.data;

  return (
    <section className="conversationDetailPage" aria-labelledby="detail-title">
      <Link className="backLink" href="/conversations">Back to conversations</Link>
      <div className="detailHero">
        <div>
          <p className="eyebrow">Conversation detail</p>
          <h2 id="detail-title">{conversation.title || `Conversation ${conversation.id.slice(0, 8)}`}</h2>
          <p>Messages are shown in deterministic sequence with citations attached to the assistant answer that used them.</p>
        </div>
        <ConversationStatusBadge status={conversation.status} />
      </div>

      <dl className="detailMeta">
        <div>
          <dt>Channel</dt>
          <dd>{formatEnum(conversation.channel)}</dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{formatDate(conversation.started_at)}</dd>
        </div>
        <div>
          <dt>Last message</dt>
          <dd>{conversation.last_message_at ? formatDate(conversation.last_message_at) : "None"}</dd>
        </div>
        <div>
          <dt>Messages</dt>
          <dd>{conversation.messages.length}</dd>
        </div>
      </dl>

      <MessageThread messages={conversation.messages} />
    </section>
  );
}


async function loadConversationDetail(
  session: DevelopmentDashboardSession,
  conversationId: string,
) {
  try {
    const response = await getConversationDetail(session, conversationId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) {
      return { ok: false as const, error };
    }
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
