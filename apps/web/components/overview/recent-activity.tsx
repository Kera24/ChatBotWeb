import { Clock3, FileText, MessageSquare, Rocket, ShieldAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";

import type { OverviewData } from "../../lib/api/overview";

type ActivityItem = {
  id: string;
  icon: LucideIcon;
  label: string;
  detail: string;
  href: string;
  timestamp: string;
};

export function buildRecentActivity(data: OverviewData): ActivityItem[] {
  const documentItems: ActivityItem[] = data.documents.map((document) => ({
    id: `document-${document.id}`,
    icon: FileText,
    label: document.title,
    detail: `Document ${document.status.replace(/_/g, " ")}.`,
    href: "/knowledge",
    timestamp: document.updated_at,
  }));
  const conversationItems: ActivityItem[] = data.conversations.map((conversation) => ({
    id: `conversation-${conversation.id}`,
    icon: MessageSquare,
    label: conversation.title || `Conversation ${conversation.id.slice(0, 8)}`,
    detail: `${conversation.channel.replace(/_/g, " ")} · ${conversation.message_count} message${conversation.message_count === 1 ? "" : "s"}.`,
    href: `/conversations/${conversation.id}`,
    timestamp: conversation.last_message_at || conversation.started_at,
  }));
  const widgetItems: ActivityItem[] = data.widgets.map((widget) => ({
    id: `widget-${widget.id}`,
    icon: Rocket,
    label: widget.display_name,
    detail: `Assistant ${widget.publication_status.replace(/_/g, " ")}; operational status ${widget.operational_status.replace(/_/g, " ")}.`,
    href: `/assistants/${widget.id}?assistant=${widget.id}`,
    timestamp: widget.updated_at,
  }));
  const reviewItems: ActivityItem[] = data.reviewItems.map((item) => ({
    id: `review-${item.assistant_message_id}`,
    icon: ShieldAlert,
    label: "Knowledge gap flagged",
    detail: `${item.answer_state.replace(/_/g, " ")} answer on ${item.channel.replace(/_/g, " ")}.`,
    href: `/review/unanswered/${item.assistant_message_id}`,
    timestamp: item.created_at,
  }));

  return [...documentItems, ...conversationItems, ...widgetItems, ...reviewItems]
    .filter((item) => Boolean(item.timestamp))
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    .slice(0, 8);
}

export function RecentActivity({ items }: { items: ActivityItem[] }) {
  return (
    <section className="overviewPanel" aria-labelledby="activity-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Recent activity</p>
          <h3 id="activity-title">Latest workspace changes</h3>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="overviewEmptyState">
          <Clock3 size={20} aria-hidden="true" />
          <h4>No recent activity</h4>
          <p>Documents, assistants, conversations, and review items will appear here once the workspace is used.</p>
        </div>
      ) : (
        <ol className="overviewTimeline" aria-label="Recent platform activity">
          {items.map((item) => (
            <li key={item.id}>
              <span className="overviewTimelineIcon" aria-hidden="true"><item.icon size={15} /></span>
              <div>
                <Link href={item.href}>{item.label}</Link>
                <p>{item.detail}</p>
              </div>
              <time dateTime={item.timestamp}>{formatDate(item.timestamp)}</time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
