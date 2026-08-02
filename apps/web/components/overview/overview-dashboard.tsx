import Link from "next/link";

import type { OverviewData } from "../../lib/api/overview";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type OverviewDashboardProps = {
  session: DevelopmentDashboardSession;
  data: OverviewData;
  environment: string;
};

type ActivityItem = {
  id: string;
  label: string;
  detail: string;
  href: string;
  timestamp: string;
};

type AlertItem = {
  id: string;
  tone: "warning" | "danger";
  title: string;
  detail: string;
  href: string;
};

export function OverviewDashboard({ session, data, environment }: OverviewDashboardProps) {
  const metrics = buildMetrics(data);
  const health = buildHealth(data);
  const activity = buildActivity(data);
  const alerts = buildAlerts(data);
  const latestKnowledgeUpdate = latestDate(data.documents.map((document) => document.updated_at));

  return (
    <section className="overviewPage" aria-labelledby="overview-title">
      <div className="overviewHero">
        <div>
          <p className="eyebrow">Yoranix overview</p>
          <h2 id="overview-title">Operational view of the AI knowledge platform</h2>
          <p>Monitor workspace readiness, knowledge health, widget publication, and answer-review pressure from existing tenant-scoped systems.</p>
        </div>
        <div className="overviewHeroAside" aria-label="Workspace identity">
          <strong>{session.role.replace("_", " ")}</strong>
          <span>{environment}</span>
        </div>
      </div>

      <section className="overviewMetricGrid" aria-label="Workspace metrics">
        {metrics.map((metric) => (
          <article className="overviewMetricCard" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.detail}</p>
          </article>
        ))}
      </section>

      <div className="overviewLayout">
        <section className="overviewPanel" aria-labelledby="health-title">
          <div className="overviewPanelHeader">
            <div>
              <p className="sectionKicker">AI system health</p>
              <h3 id="health-title">Derived from lifecycle state</h3>
            </div>
            <span className={`overviewHealthBadge overview-health-${health.overall}`}>{health.label}</span>
          </div>
          <div className="overviewHealthList" role="list">
            {health.items.map((item) => (
              <article className="overviewHealthItem" role="listitem" key={item.title}>
                <span className={`overviewStatusDot overview-status-${item.state}`} aria-hidden="true" />
                <div>
                  <h4>{item.title}</h4>
                  <p>{item.detail}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="overviewPanel" aria-labelledby="workspace-title">
          <div className="overviewPanelHeader">
            <div>
              <p className="sectionKicker">Workspace</p>
              <h3 id="workspace-title">Current context</h3>
            </div>
          </div>
          <dl className="overviewFacts">
            <div><dt>Platform</dt><dd>Yoranix Knowledge Platform</dd></div>
            <div><dt>Workspace status</dt><dd>Active</dd></div>
            <div><dt>Member role</dt><dd>{session.role.replace("_", " ")}</dd></div>
            <div><dt>Environment</dt><dd>{environment}</dd></div>
            <div><dt>Latest knowledge update</dt><dd>{latestKnowledgeUpdate ? formatDate(latestKnowledgeUpdate) : "None yet"}</dd></div>
          </dl>
        </section>
      </div>

      <section className="overviewQuickActions" aria-labelledby="quick-actions-title">
        <div>
          <p className="sectionKicker">Quick actions</p>
          <h3 id="quick-actions-title">Move to the right operational surface</h3>
        </div>
        <div className="overviewActionList">
          <Link className="actionButton" href="/knowledge">Upload document</Link>
          <Link className="actionButton" href="/chatbot">Open chatbot</Link>
          <Link className="actionButton" href="/review/unanswered">Review knowledge gaps</Link>
          <Link className="actionButton" href="/widgets">Manage widgets</Link>
          <Link className="actionButton" href="/conversations">View conversations</Link>
        </div>
      </section>

      <div className="overviewLayout">
        <section className="overviewPanel" aria-labelledby="activity-title">
          <div className="overviewPanelHeader">
            <div>
              <p className="sectionKicker">Recent activity</p>
              <h3 id="activity-title">Latest workspace changes</h3>
            </div>
          </div>
          {activity.length === 0 ? (
            <OverviewEmpty title="No recent activity" detail="Documents, widgets, conversations, and review items will appear after the workspace is used." />
          ) : (
            <ol className="overviewTimeline" aria-label="Recent platform activity">
              {activity.map((item) => (
                <li key={item.id}>
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

        <section className="overviewPanel" aria-labelledby="alerts-title">
          <div className="overviewPanelHeader">
            <div>
              <p className="sectionKicker">Alerts</p>
              <h3 id="alerts-title">Actionable items</h3>
            </div>
          </div>
          {alerts.length === 0 ? (
            <OverviewEmpty title="No actionable alerts" detail="No failed documents, stalled processing, inactive widgets, or open review backlog was found." />
          ) : (
            <div className="overviewAlertList" role="list">
              {alerts.map((alert) => (
                <article className={`overviewAlert overview-alert-${alert.tone}`} role="listitem" key={alert.id}>
                  <div>
                    <h4>{alert.title}</h4>
                    <p>{alert.detail}</p>
                  </div>
                  <Link className="smallButton" href={alert.href}>Open</Link>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

export function OverviewSkeleton() {
  return (
    <section className="overviewPage" aria-busy="true" aria-live="polite">
      <div className="overviewHero overviewSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Yoranix overview</h2>
          <p>Collecting tenant-scoped dashboard signals.</p>
        </div>
      </div>
      <div className="overviewMetricGrid">
        {[0, 1, 2, 3].map((item) => <div className="overviewMetricCard overviewSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}

function OverviewEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="overviewEmptyState">
      <h4>{title}</h4>
      <p>{detail}</p>
    </div>
  );
}

function buildMetrics(data: OverviewData) {
  const readyDocuments = data.documents.filter((document) => document.status === "ready").length;
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const conversationsToday = data.conversations.filter((conversation) => isToday(conversation.started_at)).length;
  const activeWidgets = data.widgets.filter((widget) => widget.operational_status === "enabled" && widget.publication_status === "published").length;

  return [
    { label: "Total documents", value: String(data.documents.length), detail: "Workspace documents in the knowledge lifecycle." },
    { label: "Processing", value: String(processingDocuments), detail: "Uploaded or processing documents." },
    { label: "Ready documents", value: String(readyDocuments), detail: "Documents available for retrieval workflows." },
    { label: "Failed documents", value: String(failedDocuments), detail: "Documents requiring operational attention." },
    { label: "Conversations today", value: String(conversationsToday), detail: "Visible conversations started today." },
    { label: "Open knowledge gaps", value: String(data.reviewTotal), detail: "Unanswered review items still open." },
    { label: "Active widgets", value: `${activeWidgets}/${data.widgets.length}`, detail: "Published and operational widgets." },
  ];
}

function buildHealth(data: OverviewData) {
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const readyDocuments = data.documents.filter((document) => document.status === "ready").length;
  const openReviews = data.reviewTotal;
  const inactiveWidgets = data.widgets.filter((widget) => widget.operational_status !== "enabled" || widget.publication_status !== "published").length;
  const overall = failedDocuments > 0 ? "danger" : openReviews > 0 || inactiveWidgets > 0 ? "warning" : "healthy";

  return {
    overall,
    label: overall === "healthy" ? "Healthy" : overall === "warning" ? "Needs review" : "Attention required",
    items: [
      {
        title: "Document processing",
        state: failedDocuments > 0 ? "danger" : processingDocuments > 0 ? "warning" : "healthy",
        detail: failedDocuments > 0 ? `${failedDocuments} document failed processing.` : `${processingDocuments} document is currently uploaded or processing.`,
      },
      {
        title: "Index status",
        state: readyDocuments > 0 ? "healthy" : data.documents.length > 0 ? "warning" : "idle",
        detail: readyDocuments > 0 ? `${readyDocuments} ready document can support retrieval.` : "No ready documents are visible from the document lifecycle.",
      },
      {
        title: "Review backlog",
        state: openReviews > 0 ? "warning" : "healthy",
        detail: openReviews > 0 ? `${openReviews} open unanswered item requires review.` : "No open unanswered review backlog was returned.",
      },
      {
        title: "Widget availability",
        state: inactiveWidgets > 0 ? "warning" : "healthy",
        detail: data.widgets.length === 0 ? "No widgets exist yet." : `${data.widgets.length - inactiveWidgets} of ${data.widgets.length} widgets are published and enabled.`,
      },
    ],
  };
}

function buildActivity(data: OverviewData): ActivityItem[] {
  const documentItems = data.documents.map((document) => ({
    id: `document-${document.id}`,
    label: document.title,
    detail: `Document ${document.status.replace("_", " ")}.`,
    href: "/knowledge",
    timestamp: document.updated_at,
  }));
  const conversationItems = data.conversations.map((conversation) => ({
    id: `conversation-${conversation.id}`,
    label: conversation.title || `Conversation ${conversation.id.slice(0, 8)}`,
    detail: `${conversation.channel} conversation with ${conversation.message_count} messages.`,
    href: `/conversations/${conversation.id}`,
    timestamp: conversation.last_message_at || conversation.started_at,
  }));
  const widgetItems = data.widgets.map((widget) => ({
    id: `widget-${widget.id}`,
    label: widget.display_name,
    detail: `Widget ${widget.publication_status}; operational status ${widget.operational_status}.`,
    href: `/widgets/${widget.id}`,
    timestamp: widget.updated_at,
  }));
  const reviewItems = data.reviewItems.map((item) => ({
    id: `review-${item.assistant_message_id}`,
    label: "Knowledge gap flagged",
    detail: `${item.answer_state} answer on ${item.channel}.`,
    href: `/review/unanswered/${item.assistant_message_id}`,
    timestamp: item.created_at,
  }));

  return [...documentItems, ...conversationItems, ...widgetItems, ...reviewItems]
    .filter((item) => Boolean(item.timestamp))
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    .slice(0, 8);
}

function buildAlerts(data: OverviewData): AlertItem[] {
  const alerts: AlertItem[] = [];
  const failedDocuments = data.documents.filter((document) => document.status === "failed");
  const stalledDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status) && minutesSince(document.updated_at) > 30);
  const inactiveWidgets = data.widgets.filter((widget) => widget.operational_status !== "enabled" || widget.publication_status !== "published");

  if (failedDocuments.length > 0) {
    alerts.push({ id: "failed-documents", tone: "danger", title: "Failed document processing", detail: `${failedDocuments.length} document needs investigation.`, href: "/knowledge" });
  }
  if (stalledDocuments.length > 0) {
    alerts.push({ id: "stalled-documents", tone: "warning", title: "Documents may be stalled", detail: `${stalledDocuments.length} document has not changed for more than 30 minutes.`, href: "/knowledge" });
  }
  if (data.reviewTotal > 0) {
    alerts.push({ id: "review-backlog", tone: "warning", title: "Knowledge review backlog", detail: `${data.reviewTotal} unanswered item is open for review.`, href: "/review/unanswered" });
  }
  if (inactiveWidgets.length > 0) {
    alerts.push({ id: "inactive-widgets", tone: "warning", title: "Inactive widget configuration", detail: `${inactiveWidgets.length} widget is not both published and enabled.`, href: "/widgets" });
  }

  return alerts;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function latestDate(values: string[]) {
  const timestamps = values.map((value) => new Date(value).getTime()).filter(Number.isFinite);
  if (timestamps.length === 0) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}

function isToday(value: string) {
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
}

function minutesSince(value: string) {
  return (Date.now() - new Date(value).getTime()) / 60_000;
}




