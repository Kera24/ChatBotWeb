"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Database,
  FileText,
  Info,
  Layers,
  Lightbulb,
  MessageSquare,
  Minus,
  Rocket,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { AnalyticsData, AnalyticsFilters } from "../../lib/api/analytics";
import type { ConversationDetail, ConversationMessage, ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle, AssistantStatusBadge } from "../assistants/assistant-management";

type AnalyticsDashboardProps = {
  data: AnalyticsData;
  assistant: WidgetDetail;
};

type BreakdownItem = {
  label: string;
  value: number;
};

type TrendPoint = {
  label: string;
  value: number;
};

type TrendDelta = {
  direction: "up" | "down" | "flat";
  percent: number;
};

type InsightTone = "danger" | "warning" | "info" | "success";

type Insight = {
  id: string;
  tone: InsightTone;
  title: string;
  detail: string;
  href: string;
};

type MetricCard = {
  key: string;
  label: string;
  value: string;
  detail: string;
  delta?: { text: string; direction: "up" | "down" | "flat"; good: boolean } | null;
};

type ActivityItem = {
  id: string;
  icon: LucideIcon;
  label: string;
  helper: string;
  time: string | null;
};

const TONE_PRIORITY: Record<InsightTone, number> = { danger: 3, warning: 2, info: 1, success: 0 };
const TONE_ICON: Record<InsightTone, LucideIcon> = { danger: ShieldAlert, warning: AlertTriangle, info: Info, success: CheckCircle2 };

export function AnalyticsDashboard({ data, assistant }: AnalyticsDashboardProps) {
  const reduceMotion = useReducedMotion();
  const lifecycle = assistantLifecycle(assistant);
  const metrics = calculateAnalyticsMetrics(data);
  const dailyConversationVolume = buildDailyCounts(data.conversations, (conversation) => conversation.started_at);
  const dailyFallbackRateTrend = buildDailyFallbackRate(data.conversationDetails);
  const dailyGapTrend = buildDailyCounts(data.reviewItems, (item) => item.created_at);
  const channelBreakdown = buildBreakdown(data.conversations.map((conversation) => conversation.channel));
  const statusBreakdown = buildBreakdown(data.conversations.map((conversation) => conversation.status));
  const documentBreakdown = buildBreakdown(data.documents.map((document) => document.status));
  const answerStateBreakdown = buildBreakdown(collectAssistantMessages(data).map((message) => message.answer_state || "unknown"));
  const latencyBuckets = buildLatencyBuckets(collectAssistantMessages(data).map((message) => message.latency_ms).filter(isNumber));
  const documentPerformance = buildDocumentPerformance(data);
  const topQuestions = buildTopQuestions(data);
  const activity = buildRecentActivity(data, assistant);
  const lastActivity = latestTimestamp([...data.conversations.map((c) => c.last_message_at || c.started_at), ...data.documents.map((d) => d.updated_at), assistant.updated_at]);
  const insights = buildInsights(data, metrics, {
    dailyFallbackRateTrend,
    dailyGapTrend,
    documentPerformance,
    assistant,
    lastActivity,
  });
  const hasAnySignal = data.conversations.length > 0 || data.documents.length > 0 || data.reviewItems.length > 0;

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="analyticsPage premiumAnalyticsPage" aria-labelledby="analytics-title" {...pageMotion}>
      <ExecutiveHeader assistant={assistant} lifecycle={lifecycle} data={data} lastActivity={lastActivity} />

      <AnalyticsFiltersForm filters={data.filters} />

      <section className="analyticsNotice" aria-label="Analytics data limitations">
        <Info size={15} aria-hidden="true" />
        <p>Conversation and review filters are applied by the backend. Response-quality and citation signals use the latest {data.conversationDetails.length} conversation details from a maximum recent window of {data.recentWindowLimit} conversations.</p>
      </section>

      {hasAnySignal ? (
        <>
          <MetricRow cards={metrics.cards} />

          <div className="analyticsExecutiveGrid">
            <div className="analyticsMainColumn">
              <TrendPanel
                title="Conversation trend"
                kicker="Usage"
                points={dailyConversationVolume}
                tone="primary"
                ariaLabel="Conversations by day"
                action={{ href: `/conversations?assistant=${assistant.id}`, label: "Open conversations" }}
                emptyDetail="No conversations were returned for the selected filters."
              />

              <div className="analyticsSplitGrid">
                <ChartPanel title="Fallback trend" kicker="Response quality" emptyState={dailyFallbackRateTrend.length === 0} emptyDetail="No sampled assistant responses in this window.">
                  <TrendChart points={dailyFallbackRateTrend} ariaLabel="Daily fallback rate percentage" tone="warning" suffix="%" />
                </ChartPanel>
                <ChartPanel title="Source coverage" kicker="Response quality" emptyState={metrics.citationCoverage === null} emptyDetail="No sampled assistant responses in this window.">
                  <div className="analyticsGaugeRow">
                    <DonutGauge percent={metrics.citationCoverage ?? 0} label="Citation coverage" tone="primary" />
                    <dl className="analyticsFacts compact">
                      <div><dt>Cited responses</dt><dd>{metrics.citedResponses}</dd></div>
                      <div><dt>Sampled responses</dt><dd>{metrics.assistantMessageCount}</dd></div>
                      <div><dt>Average latency</dt><dd>{metrics.averageLatencyLabel}</dd></div>
                    </dl>
                  </div>
                </ChartPanel>
              </div>

              <div className="analyticsSplitGrid">
                <ChartPanel title="Knowledge usage" kicker="Knowledge performance" action={{ href: `/knowledge?assistant=${assistant.id}`, label: "Open knowledge base" }} emptyState={documentBreakdown.length === 0} emptyDetail="No documents matched the selected document-status filter.">
                  <BarList items={documentBreakdown} ariaLabel="Document status distribution" />
                </ChartPanel>
                <ChartPanel title="Answer confidence" kicker="Response quality" emptyState={answerStateBreakdown.length === 0} emptyDetail="No sampled assistant responses in this window.">
                  <BarList items={answerStateBreakdown} ariaLabel="Assistant answer-state distribution" />
                </ChartPanel>
              </div>

              <div className="analyticsSplitGrid">
                <ChartPanel title="Latency distribution" kicker="Performance" emptyState={latencyBuckets.every((bucket) => bucket.value === 0)} emptyDetail="No latency samples in this window.">
                  <BarList items={latencyBuckets} ariaLabel="Response latency distribution" />
                </ChartPanel>
                <ChartPanel title="Conversation sources" kicker="Usage" emptyState={channelBreakdown.length === 0} emptyDetail="No conversations were returned.">
                  <div className="analyticsSplit">
                    <div><h4>Source</h4>{channelBreakdown.length === 0 ? <AnalyticsEmpty title="No sources" detail="No conversations were returned." /> : <BarList items={channelBreakdown} ariaLabel="Conversation source distribution" compact />}</div>
                    <div><h4>Status</h4>{statusBreakdown.length === 0 ? <AnalyticsEmpty title="No statuses" detail="No conversation statuses were returned." /> : <BarList items={statusBreakdown} ariaLabel="Conversation status distribution" compact />}</div>
                  </div>
                </ChartPanel>
              </div>

              <section className="analyticsPanel" aria-labelledby="ai-insights-title">
                <div className="analyticsPanelHeader">
                  <div>
                    <p className="sectionKicker">AI insights</p>
                    <h3 id="ai-insights-title">Signals worth reviewing</h3>
                  </div>
                </div>
                <InsightGrid insights={insights} />
              </section>

              <div className="analyticsSplitGrid">
                <ChartPanel title="Top documents" kicker="Document performance" emptyState={documentPerformance.top.length === 0} emptyDetail="No citations were found in the sampled conversation window.">
                  <BarList items={documentPerformance.top.map((item) => ({ label: item.title, value: item.count }))} ariaLabel="Most referenced documents" />
                  {documentPerformance.unused.length > 0 ? (
                    <p className="analyticsCaveat">{documentPerformance.unused.length} ready document{documentPerformance.unused.length === 1 ? "" : "s"} were never referenced in this sample: {documentPerformance.unused.slice(0, 3).map((document) => document.title).join(", ")}{documentPerformance.unused.length > 3 ? "…" : ""}</p>
                  ) : null}
                </ChartPanel>
                <ChartPanel title="Top questions" kicker="Conversation insights" emptyState={topQuestions.length === 0} emptyDetail="No repeated questions were found in the sampled conversation window.">
                  <BarList items={topQuestions} ariaLabel="Most frequently asked questions" />
                </ChartPanel>
              </div>

              <section className="analyticsPanel" aria-labelledby="review-title">
                <div className="analyticsPanelHeader">
                  <div>
                    <p className="sectionKicker">Knowledge gaps</p>
                    <h3 id="review-title">Recent unanswered questions</h3>
                  </div>
                  <Link className="smallButton" href="/review/unanswered">Open review queue</Link>
                </div>
                {data.reviewItems.length === 0 ? <AnalyticsEmpty title="No open gaps" detail="No open unanswered review items matched the selected filters." /> : <ReviewTable items={data.reviewItems.slice(0, 5)} />}
              </section>

              <RecentActivityPanel items={activity} />
            </div>

            <aside className="analyticsSidePanel" aria-label="Recommended actions">
              <RecommendationPanel insights={insights} assistant={assistant} />
            </aside>
          </div>
        </>
      ) : (
        <AnalyticsNoDataState assistant={assistant} />
      )}
    </motion.section>
  );
}

function ExecutiveHeader({ assistant, lifecycle, data, lastActivity }: { assistant: WidgetDetail; lifecycle: ReturnType<typeof assistantLifecycle>; data: AnalyticsData; lastActivity: string | null }) {
  const reduceMotion = useReducedMotion();
  const readyDocuments = data.documents.filter((document) => document.status === "ready").length;
  const headerMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.header className="analyticsHero premiumAnalyticsHero" {...headerMotion}>
      <div className="analyticsHeroMain">
        <div className="analyticsHeroIdentity">
          <span className="analyticsHeroAvatar" aria-hidden="true"><BarChart3 size={24} /></span>
          <div>
            <p className="eyebrow">Conversa analytics</p>
            <h2 id="analytics-title">{assistant.display_name}</h2>
            <div className="analyticsHeroMeta" aria-label="Assistant state summary">
              <AssistantStatusBadge status={lifecycle} />
              <span><Database size={14} aria-hidden="true" />Knowledge {readyDocuments}/{data.documents.length} ready</span>
              <span><Clock size={14} aria-hidden="true" />Last activity {formatRelativeTime(lastActivity)}</span>
              <span><Activity size={14} aria-hidden="true" />{periodLabel(data.filters, data.recentWindowLimit)}</span>
            </div>
          </div>
        </div>
        <Link className="smallButton" href="/dashboard" aria-label="Switch to a different assistant">Switch assistant</Link>
      </div>

      <nav className="analyticsQuickLinks" aria-label="Assistant quick links">
        <Link href={`/knowledge?assistant=${assistant.id}`}><FileText size={15} aria-hidden="true" />Knowledge</Link>
        <Link href={`/assistants/${assistant.id}?tab=playground&assistant=${assistant.id}`}><MessageSquare size={15} aria-hidden="true" />Playground</Link>
        <Link href={`/conversations?assistant=${assistant.id}`}><Activity size={15} aria-hidden="true" />Conversations</Link>
        <Link href={`/assistants/${assistant.id}?tab=widget&assistant=${assistant.id}`}><Rocket size={15} aria-hidden="true" />Widget</Link>
      </nav>

      {lifecycle === "Archived" ? (
        <p className="analyticsArchivedNotice" role="status">
          <ShieldAlert size={15} aria-hidden="true" />This assistant is archived. Showing historical data only.
        </p>
      ) : null}
    </motion.header>
  );
}

function MetricRow({ cards }: { cards: MetricCard[] }) {
  const reduceMotion = useReducedMotion();
  return (
    <section className="analyticsMetricGrid" aria-label="Usage metrics">
      {cards.map((metric, index) => (
        <motion.article
          className="analyticsMetricCard"
          key={metric.key}
          initial={reduceMotion ? false : { opacity: 0, y: 10 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
          transition={reduceMotion ? undefined : { delay: index * 0.035 }}
        >
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          <p>{metric.detail}</p>
          {metric.delta ? <TrendBadge direction={metric.delta.direction} text={metric.delta.text} good={metric.delta.good} /> : null}
        </motion.article>
      ))}
    </section>
  );
}

function TrendBadge({ direction, text, good }: { direction: "up" | "down" | "flat"; text: string; good: boolean }) {
  const Icon = direction === "up" ? TrendingUp : direction === "down" ? TrendingDown : Minus;
  const tone = direction === "flat" ? "neutral" : good ? "positive" : "negative";
  return (
    <span className={`analyticsTrendBadge tone-${tone}`}>
      <Icon size={13} aria-hidden="true" />
      {text}
    </span>
  );
}

function ChartPanel({ title, kicker, children, action, emptyState, emptyDetail }: { title: string; kicker: string; children: ReactNode; action?: { href: string; label: string }; emptyState?: boolean; emptyDetail?: string }) {
  return (
    <section className="analyticsPanel" aria-labelledby={`panel-${slugify(title)}`}>
      <div className="analyticsPanelHeader">
        <div>
          <p className="sectionKicker">{kicker}</p>
          <h3 id={`panel-${slugify(title)}`}>{title}</h3>
        </div>
        {action ? <Link className="smallButton" href={action.href}>{action.label}</Link> : null}
      </div>
      {emptyState ? <AnalyticsEmpty title={`No ${title.toLowerCase()} data`} detail={emptyDetail || "No data was returned for the selected filters."} /> : children}
    </section>
  );
}

function TrendPanel({ title, kicker, points, tone, ariaLabel, action, emptyDetail }: { title: string; kicker: string; points: TrendPoint[]; tone: "primary" | "warning"; ariaLabel: string; action?: { href: string; label: string }; emptyDetail: string }) {
  const delta = computeTrendDelta(points);
  return (
    <section className="analyticsPanel analyticsTrendPanel" aria-labelledby={`panel-${slugify(title)}`}>
      <div className="analyticsPanelHeader">
        <div>
          <p className="sectionKicker">{kicker}</p>
          <h3 id={`panel-${slugify(title)}`}>{title}</h3>
        </div>
        <div className="analyticsPanelHeaderActions">
          {delta ? <TrendBadge direction={delta.direction} text={`${delta.percent}%`} good={delta.direction !== "up" || tone === "primary"} /> : null}
          {action ? <Link className="smallButton" href={action.href}>{action.label}</Link> : null}
        </div>
      </div>
      {points.length === 0 ? <AnalyticsEmpty title="No conversation volume" detail={emptyDetail} /> : <TrendChart points={points} ariaLabel={ariaLabel} tone={tone} />}
    </section>
  );
}

function TrendChart({ points, ariaLabel, tone, suffix = "" }: { points: TrendPoint[]; ariaLabel: string; tone: "primary" | "warning"; suffix?: string }) {
  const width = 100;
  const height = 32;
  const values = points.map((point) => point.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = points.length > 1 ? width / (points.length - 1) : 0;
  const coords = points.map((point, index) => ({
    x: points.length > 1 ? index * stepX : width / 2,
    y: height - ((point.value - min) / range) * height,
  }));
  const linePath = coords.map((coord, index) => `${index === 0 ? "M" : "L"}${coord.x.toFixed(2)},${coord.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;
  const strokeColor = tone === "warning" ? "var(--yoranix-warning, #f59e0b)" : "var(--yoranix-primary, var(--primary))";
  const latest = points[points.length - 1];

  return (
    <figure className="analyticsSparkline">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={ariaLabel}>
        <title>{ariaLabel}</title>
        <path d={areaPath} fill={strokeColor} opacity="0.12" stroke="none" />
        <path d={linePath} fill="none" stroke={strokeColor} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="analyticsSparklineCaption">
        <span>{points[0]?.label ? formatShortDate(points[0].label) : ""}</span>
        <strong>{latest.value}{suffix} latest</strong>
        <span>{latest.label ? formatShortDate(latest.label) : ""}</span>
      </figcaption>
    </figure>
  );
}

function DonutGauge({ percent, label, tone }: { percent: number; label: string; tone: "primary" | "warning" }) {
  const clamped = Math.max(0, Math.min(1, percent));
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  const strokeColor = tone === "warning" ? "var(--yoranix-warning, #f59e0b)" : "var(--yoranix-primary, var(--primary))";
  return (
    <div className="analyticsGauge" role="img" aria-label={`${label}: ${Math.round(clamped * 100)}%`}>
      <svg viewBox="0 0 72 72" width="72" height="72">
        <circle cx="36" cy="36" r={radius} fill="none" stroke="var(--yoranix-border, var(--border))" strokeWidth="7" />
        <circle
          cx="36"
          cy="36"
          r={radius}
          fill="none"
          stroke={strokeColor}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 36 36)"
        />
      </svg>
      <div className="analyticsGaugeValue">
        <strong>{Math.round(clamped * 100)}%</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function InsightGrid({ insights }: { insights: Insight[] }) {
  return (
    <div className="analyticsInsightGrid" role="list">
      {insights.map((insight) => {
        const Icon = TONE_ICON[insight.tone];
        return (
          <article className={`analyticsInsight tone-${insight.tone}`} role="listitem" key={insight.id}>
            <span className="analyticsInsightIcon" aria-hidden="true"><Icon size={16} /></span>
            <div>
              <h4>{insight.title}</h4>
              <p>{insight.detail}</p>
            </div>
            <Link className="smallButton" href={insight.href}>Open<ArrowRight size={13} aria-hidden="true" /></Link>
          </article>
        );
      })}
    </div>
  );
}

function RecommendationPanel({ insights, assistant }: { insights: Insight[]; assistant: WidgetDetail }) {
  const prioritised = [...insights].filter((insight) => insight.tone !== "success").sort((a, b) => TONE_PRIORITY[b.tone] - TONE_PRIORITY[a.tone]).slice(0, 3);
  const items = prioritised.length > 0 ? prioritised : insights.filter((insight) => insight.tone === "success");

  return (
    <section className="analyticsRecommendationPanel" aria-labelledby="recommendations-title">
      <div className="assistantPanelHeaderInline">
        <div>
          <p className="sectionKicker">Recommended actions</p>
          <h3 id="recommendations-title">Next best steps</h3>
        </div>
        <Lightbulb size={18} aria-hidden="true" />
      </div>
      <ol className="analyticsRecommendationList">
        {items.map((insight) => {
          const Icon = TONE_ICON[insight.tone];
          return (
            <li key={insight.id} className={`tone-${insight.tone}`}>
              <span aria-hidden="true"><Icon size={15} /></span>
              <div>
                <strong>{insight.title}</strong>
                <p>{insight.detail}</p>
                <Link href={insight.href}>Take action<ArrowRight size={12} aria-hidden="true" /></Link>
              </div>
            </li>
          );
        })}
      </ol>
      <Link className="smallButton analyticsRecommendationFooter" href={`/assistants/${assistant.id}?assistant=${assistant.id}`}>Open assistant overview</Link>
    </section>
  );
}

function RecentActivityPanel({ items }: { items: ActivityItem[] }) {
  return (
    <section className="analyticsPanel" aria-labelledby="recent-activity-title">
      <div className="analyticsPanelHeader">
        <div>
          <p className="sectionKicker">Recent activity</p>
          <h3 id="recent-activity-title">Timeline</h3>
        </div>
      </div>
      {items.length === 0 ? <AnalyticsEmpty title="No recent activity" detail="No conversations, knowledge updates, or assistant changes were found in the selected window." /> : (
        <ul className="analyticsActivityList">
          {items.map((item) => (
            <li key={item.id}>
              <span aria-hidden="true"><item.icon size={15} /></span>
              <div>
                <strong>{item.label}</strong>
                <p>{item.helper}</p>
              </div>
              <time dateTime={item.time ?? undefined}>{item.time ? formatDate(item.time) : "No timestamp"}</time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AnalyticsFiltersForm({ filters }: { filters: AnalyticsFilters }) {
  return (
    <form className="analyticsFilters" aria-label="Analytics filters">
      <label>
        Started after
        <input type="date" name="started_after" defaultValue={toDateInput(filters.started_after)} />
      </label>
      <label>
        Started before
        <input type="date" name="started_before" defaultValue={toDateInput(filters.started_before)} />
      </label>
      <label>
        Source
        <select name="conversation_channel" defaultValue={filters.conversation_channel || ""}>
          <option value="">All sources</option>
          <option value="dashboard_test">Dashboard test</option>
          <option value="widget">Widget</option>
          <option value="api">API</option>
          <option value="future_integration">Future integration</option>
        </select>
      </label>
      <label>
        Conversation status
        <select name="conversation_status" defaultValue={filters.conversation_status || ""}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="abandoned">Abandoned</option>
          <option value="archived">Archived</option>
        </select>
      </label>
      <label>
        Document status
        <select name="document_status" defaultValue={filters.document_status || ""}>
          <option value="">All documents</option>
          <option value="uploaded">Uploaded</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
          <option value="archived">Archived</option>
        </select>
      </label>
      {filters.assistantId ? <input type="hidden" name="assistant" value={filters.assistantId} /> : null}
      <div className="analyticsFilterActions">
        <button className="actionButton" type="submit">Apply filters</button>
        <Link className="smallButton" href={filters.assistantId ? `/analytics?assistant=${filters.assistantId}` : "/analytics"}>Reset</Link>
      </div>
    </form>
  );
}

function BarList({ items, ariaLabel, compact }: { items: BreakdownItem[]; ariaLabel: string; compact?: boolean }) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className={compact ? "analyticsBarList compact" : "analyticsBarList"} role="list" aria-label={ariaLabel}>
      {items.map((item) => (
        <div className="analyticsBarItem" role="listitem" key={item.label}>
          <div className="analyticsBarLabel"><span>{formatLabel(item.label)}</span><strong>{item.value}</strong></div>
          <div className="analyticsBarTrack" aria-hidden="true"><span style={{ width: `${Math.max(4, (item.value / max) * 100)}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

function ReviewTable({ items }: { items: ReviewItem[] }) {
  return (
    <div className="analyticsTableWrap">
      <table className="analyticsTable">
        <thead><tr><th>Question</th><th>State</th><th>Created</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.assistant_message_id}>
              <td><Link href={`/review/unanswered/${item.assistant_message_id}`}>{item.user_question || "Question unavailable"}</Link></td>
              <td>{formatLabel(item.answer_state)}</td>
              <td>{formatDate(item.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnalyticsEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="analyticsEmptyState">
      <h4>{title}</h4>
      <p>{detail}</p>
    </div>
  );
}

function AnalyticsNoDataState({ assistant }: { assistant: WidgetDetail }) {
  return (
    <section className="analyticsEmptyHero" role="status">
      <Sparkles size={30} aria-hidden="true" />
      <h3>No analytics yet</h3>
      <p>{assistant.display_name} has no conversations, documents, or review activity in the selected window. Test the assistant or add knowledge to start generating analytics.</p>
      <div className="analyticsEmptyHeroActions">
        <Link className="assistantAction primary" href={`/assistants/${assistant.id}?tab=playground&assistant=${assistant.id}`}>Open playground</Link>
        <Link className="assistantAction" href={`/knowledge?assistant=${assistant.id}`}>Add knowledge</Link>
      </div>
    </section>
  );
}

export function AnalyticsNoAssistantState() {
  return (
    <section className="analyticsEmptyHero" role="status">
      <Layers size={30} aria-hidden="true" />
      <h3>No assistant selected</h3>
      <p>Select an assistant from My Assistants to view its analytics.</p>
      <div className="analyticsEmptyHeroActions">
        <Link className="assistantAction primary" href="/dashboard">Go to My Assistants</Link>
      </div>
    </section>
  );
}

export function AnalyticsSkeleton() {
  return (
    <section className="analyticsPage premiumAnalyticsPage" aria-busy="true" aria-live="polite">
      <div className="analyticsHero premiumAnalyticsHero analyticsSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Conversa analytics</h2>
          <p>Collecting assistant-scoped operational metrics.</p>
        </div>
      </div>
      <div className="analyticsMetricGrid">
        {[0, 1, 2, 3].map((item) => <div className="analyticsMetricCard analyticsSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}

export function calculateAnalyticsMetrics(data: AnalyticsData) {
  const assistantMessages = collectAssistantMessages(data);
  const citedResponses = assistantMessages.filter((message) => message.citations.length > 0).length;
  const fallbackResponses = assistantMessages.filter((message) => message.answer_state === "fallback" || message.answer_state === "failed").length;
  const lowConfidenceResponses = assistantMessages.filter((message) => message.answer_state === "low_confidence").length;
  const latencies = assistantMessages.map((message) => message.latency_ms).filter(isNumber);
  const tokenTotal = assistantMessages.map((message) => message.total_tokens).filter(isNumber).reduce((sum, value) => sum + value, 0);
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const readyDocuments = data.documents.filter((document) => document.status === "ready").length;
  const citationCoverage = assistantMessages.length === 0 ? null : citedResponses / assistantMessages.length;
  const fallbackRate = assistantMessages.length === 0 ? null : fallbackResponses / assistantMessages.length;
  const resolutionRate = assistantMessages.length === 0 ? null : 1 - fallbackResponses / assistantMessages.length;
  const knowledgeCoverage = data.documents.length === 0 ? null : readyDocuments / data.documents.length;
  const averageLatency = latencies.length === 0 ? null : Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length);
  const conversationVolume = buildDailyCounts(data.conversations, (conversation) => conversation.started_at);
  const fallbackTrend = buildDailyFallbackRate(data.conversationDetails);
  const conversationsDelta = describeDelta(computeTrendDelta(conversationVolume), true);
  const fallbackDelta = describeDelta(computeTrendDelta(fallbackTrend), false);

  return {
    assistantMessageCount: assistantMessages.length,
    citedResponses,
    citationCoverage,
    citationCoverageLabel: citationCoverage === null ? "No sample" : `${Math.round(citationCoverage * 100)}%`,
    fallbackRate,
    fallbackRateLabel: fallbackRate === null ? "No sample" : `${Math.round(fallbackRate * 100)}%`,
    resolutionRate,
    resolutionRateLabel: resolutionRate === null ? "No sample" : `${Math.round(resolutionRate * 100)}%`,
    knowledgeCoverage,
    knowledgeCoverageLabel: knowledgeCoverage === null ? "No documents" : `${Math.round(knowledgeCoverage * 100)}%`,
    lowConfidenceResponses,
    averageLatency,
    averageLatencyLabel: averageLatency === null ? "No sample" : `${averageLatency} ms`,
    totalTokensLabel: tokenTotal === 0 ? "No sample" : String(tokenTotal),
    readyDocuments,
    failedDocuments,
    processingDocuments,
    cards: [
      { key: "conversations", label: "Conversations", value: String(data.conversations.length), detail: `Returned from a maximum recent window of ${data.recentWindowLimit}.`, delta: conversationsDelta },
      { key: "messages", label: "Messages", value: String(data.conversations.reduce((sum, conversation) => sum + conversation.message_count, 0)), detail: "Message counts from conversation summaries." },
      { key: "knowledge-coverage", label: "Knowledge coverage", value: knowledgeCoverage === null ? "No documents" : `${Math.round(knowledgeCoverage * 100)}%`, detail: `${readyDocuments}/${data.documents.length} documents ready.` },
      { key: "citation-rate", label: "Citation rate", value: citationCoverage === null ? "No sample" : `${Math.round(citationCoverage * 100)}%`, detail: "Share of sampled responses with citations." },
      { key: "fallback-rate", label: "Fallback rate", value: fallbackRate === null ? "No sample" : `${Math.round(fallbackRate * 100)}%`, detail: "Fallback or failed sampled responses.", delta: fallbackDelta },
      { key: "resolution-rate", label: "Resolution rate", value: resolutionRate === null ? "No sample" : `${Math.round(resolutionRate * 100)}%`, detail: "Sampled responses that were not fallback." },
      { key: "avg-latency", label: "Average latency", value: averageLatency === null ? "No sample" : `${averageLatency} ms`, detail: "Across sampled assistant responses." },
      { key: "knowledge-gaps", label: "Knowledge gaps", value: String(data.reviewTotal), detail: "Open unanswered review items in the selected period." },
    ] as MetricCard[],
  };
}

function describeDelta(delta: TrendDelta | null, higherIsBetter: boolean): MetricCard["delta"] {
  if (!delta || delta.direction === "flat") return delta ? { text: "Flat", direction: "flat", good: true } : null;
  const good = delta.direction === "up" ? higherIsBetter : !higherIsBetter;
  return { text: `${delta.percent}% ${delta.direction === "up" ? "up" : "down"}`, direction: delta.direction, good };
}

function buildInsights(
  data: AnalyticsData,
  metrics: ReturnType<typeof calculateAnalyticsMetrics>,
  extra: { dailyFallbackRateTrend: TrendPoint[]; dailyGapTrend: TrendPoint[]; documentPerformance: ReturnType<typeof buildDocumentPerformance>; assistant: WidgetDetail; lastActivity: string | null },
): Insight[] {
  const insights: Insight[] = [];
  const assistantHref = `/assistants/${extra.assistant.id}`;
  const stuckDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status) && minutesSince(document.updated_at) > 30).length;
  const staleReadyDocuments = data.documents.filter((document) => document.status === "ready" && daysSince(document.updated_at) > 90).length;
  const inactiveDays = extra.lastActivity ? daysSince(extra.lastActivity) : null;
  const gapTrend = computeTrendDelta(extra.dailyGapTrend);
  const fallbackTrend = computeTrendDelta(extra.dailyFallbackRateTrend);

  if (data.reviewTotal > 0) insights.push({ id: "review-backlog", tone: "warning", title: "Knowledge review backlog", detail: `${data.reviewTotal} open unanswered review item${data.reviewTotal === 1 ? "" : "s"} need attention.`, href: "/review/unanswered" });
  if (gapTrend && gapTrend.direction === "up" && data.reviewTotal > 0) insights.push({ id: "gap-rising", tone: "warning", title: "Knowledge gaps increasing", detail: `Unanswered questions rose ${gapTrend.percent}% across the selected window.`, href: "/review/unanswered" });
  if (metrics.failedDocuments > 0) insights.push({ id: "failed-documents", tone: "danger", title: "Document processing failures", detail: `${metrics.failedDocuments} document${metrics.failedDocuments === 1 ? "" : "s"} failed ingestion or processing.`, href: `/knowledge?assistant=${extra.assistant.id}` });
  if (stuckDocuments > 0) insights.push({ id: "stuck-documents", tone: "warning", title: "Processing may be stuck", detail: `${stuckDocuments} document has not changed for more than 30 minutes.`, href: `/knowledge?assistant=${extra.assistant.id}` });
  if (staleReadyDocuments > 0) insights.push({ id: "knowledge-stale", tone: "info", title: "Knowledge may be stale", detail: `${staleReadyDocuments} ready document${staleReadyDocuments === 1 ? "" : "s"} have not been updated in over 90 days.`, href: `/knowledge?assistant=${extra.assistant.id}` });
  if (extra.documentPerformance.unused.length > 0 && data.conversationDetails.length > 0) insights.push({ id: "unused-documents", tone: "info", title: "Documents never referenced", detail: `${extra.documentPerformance.unused.length} ready document${extra.documentPerformance.unused.length === 1 ? "" : "s"} were not cited in the sampled conversation window.`, href: `/knowledge?assistant=${extra.assistant.id}` });
  if (extra.assistant.publication_status !== "published" || extra.assistant.operational_status !== "enabled") insights.push({ id: "widget-unpublished", tone: "warning", title: "Widget not live", detail: "This assistant's widget is not both published and enabled.", href: `${assistantHref}?tab=widget&assistant=${extra.assistant.id}` });
  if (inactiveDays !== null && inactiveDays >= 7) insights.push({ id: "inactive-assistant", tone: "info", title: "Assistant inactive", detail: `No recorded activity for ${inactiveDays} day${inactiveDays === 1 ? "" : "s"}.`, href: `/conversations?assistant=${extra.assistant.id}` });
  else if (data.conversations.length === 0) insights.push({ id: "no-activity", tone: "info", title: "No conversations yet", detail: "This assistant has not been tested or used in the selected window.", href: `${assistantHref}?tab=playground&assistant=${extra.assistant.id}` });
  if (metrics.fallbackRate !== null && metrics.fallbackRate >= 0.25) insights.push({ id: "fallback-rate", tone: "warning", title: "Elevated fallback rate", detail: `${metrics.fallbackRateLabel} of sampled assistant responses were fallback or failed.`, href: "/review/unanswered" });
  else if (fallbackTrend && fallbackTrend.direction === "up" && (metrics.fallbackRate ?? 0) > 0) insights.push({ id: "fallback-rising", tone: "warning", title: "Fallback rate rising", detail: `Fallback responses increased ${fallbackTrend.percent}% across the selected window.`, href: "/review/unanswered" });
  if (metrics.citationCoverage === 0 && metrics.assistantMessageCount > 0) insights.push({ id: "no-citations", tone: "danger", title: "No citations returned", detail: "None of the sampled assistant responses included a citation.", href: "/conversations" });
  else if (metrics.citationCoverage !== null && metrics.citationCoverage < 0.5) insights.push({ id: "low-citations", tone: "warning", title: "Low citation coverage", detail: `${metrics.citationCoverageLabel} of sampled assistant responses included citations.`, href: "/conversations" });
  if (metrics.averageLatency !== null && metrics.averageLatency > 3000) insights.push({ id: "high-latency", tone: "warning", title: "High response latency", detail: `Average latency is ${metrics.averageLatencyLabel} across the sampled window.`, href: "/conversations" });
  if (insights.length === 0) insights.push({ id: "healthy", tone: "success", title: "Assistant healthy", detail: "No failed documents, inactive widgets, rising fallback rate, or open knowledge gaps were found in the selected data.", href: `${assistantHref}?assistant=${extra.assistant.id}` });

  return insights;
}

function buildDocumentPerformance(data: AnalyticsData) {
  const counts = new Map<string, { title: string; count: number }>();
  for (const conversation of data.conversationDetails) {
    for (const message of conversation.messages) {
      for (const citation of message.citations) {
        const existing = counts.get(citation.document_id);
        counts.set(citation.document_id, { title: citation.source_title, count: (existing?.count ?? 0) + 1 });
      }
    }
  }
  const referencedIds = new Set(counts.keys());
  const top = [...counts.entries()].map(([id, value]) => ({ id, title: value.title, count: value.count })).sort((a, b) => b.count - a.count).slice(0, 5);
  const unused = data.documents.filter((document) => document.status === "ready" && !referencedIds.has(document.id));
  return { top, unused };
}

function buildTopQuestions(data: AnalyticsData): BreakdownItem[] {
  const counts = new Map<string, number>();
  for (const conversation of data.conversationDetails) {
    for (const message of conversation.messages) {
      if (message.role !== "user") continue;
      const key = normaliseQuestion(message.content);
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return [...counts.entries()].filter(([, value]) => value > 0).sort(([, a], [, b]) => b - a).slice(0, 6).map(([label, value]) => ({ label, value }));
}

function buildRecentActivity(data: AnalyticsData, assistant: WidgetDetail): ActivityItem[] {
  const items: ActivityItem[] = [
    ...data.conversations.slice(0, 5).map((conversation) => ({
      id: `conversation-${conversation.id}`,
      icon: MessageSquare,
      label: conversation.title || "Conversation",
      helper: `${formatLabel(conversation.channel)} - ${formatLabel(conversation.status)}`,
      time: conversation.last_message_at || conversation.started_at,
    })),
    ...data.documents.slice(0, 5).map((document) => ({
      id: `document-${document.id}`,
      icon: FileText,
      label: document.title,
      helper: `Knowledge ${formatLabel(document.status)}`,
      time: document.updated_at,
    })),
    {
      id: `assistant-${assistant.id}`,
      icon: Rocket,
      label: assistant.display_name,
      helper: `Assistant ${formatLabel(assistant.publication_status)}`,
      time: assistant.updated_at,
    },
  ];
  return items.filter((item) => item.time).sort((a, b) => new Date(b.time as string).getTime() - new Date(a.time as string).getTime()).slice(0, 8);
}

function collectAssistantMessages(data: AnalyticsData): ConversationMessage[] {
  return data.conversationDetails.flatMap((conversation) => conversation.messages.filter((message) => message.role === "assistant"));
}

function buildDailyCounts<T>(items: T[], dateSelector: (item: T) => string): TrendPoint[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const key = dateSelector(item).slice(0, 10);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([label, value]) => ({ label, value }));
}

function buildDailyFallbackRate(conversationDetails: ConversationDetail[]): TrendPoint[] {
  const byDay = new Map<string, { total: number; fallback: number }>();
  for (const conversation of conversationDetails) {
    for (const message of conversation.messages) {
      if (message.role !== "assistant") continue;
      const day = message.created_at.slice(0, 10);
      const entry = byDay.get(day) ?? { total: 0, fallback: 0 };
      entry.total += 1;
      if (message.answer_state === "fallback" || message.answer_state === "failed") entry.fallback += 1;
      byDay.set(day, entry);
    }
  }
  return [...byDay.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([label, value]) => ({ label, value: value.total === 0 ? 0 : Math.round((value.fallback / value.total) * 100) }));
}

function buildLatencyBuckets(latencies: number[]): BreakdownItem[] {
  const buckets: Array<{ label: string; test: (value: number) => boolean }> = [
    { label: "<200ms", test: (value) => value < 200 },
    { label: "200-500ms", test: (value) => value >= 200 && value < 500 },
    { label: "500ms-1s", test: (value) => value >= 500 && value < 1000 },
    { label: "1-3s", test: (value) => value >= 1000 && value < 3000 },
    { label: ">3s", test: (value) => value >= 3000 },
  ];
  return buckets.map((bucket) => ({ label: bucket.label, value: latencies.filter(bucket.test).length }));
}

function computeTrendDelta(points: TrendPoint[]): TrendDelta | null {
  if (points.length < 2) return null;
  const mid = Math.floor(points.length / 2);
  const firstAvg = average(points.slice(0, mid).map((point) => point.value));
  const secondAvg = average(points.slice(mid).map((point) => point.value));
  if (firstAvg === 0 && secondAvg === 0) return { direction: "flat", percent: 0 };
  const change = firstAvg === 0 ? 100 : Math.round(((secondAvg - firstAvg) / firstAvg) * 100);
  if (Math.abs(change) <= 2) return { direction: "flat", percent: 0 };
  return { direction: change > 0 ? "up" : "down", percent: Math.abs(change) };
}

function average(values: number[]) {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function latestTimestamp(values: Array<string | null | undefined>): string | null {
  const valid = values.filter((value): value is string => Boolean(value));
  if (valid.length === 0) return null;
  return valid.reduce((latest, current) => (new Date(current).getTime() > new Date(latest).getTime() ? current : latest));
}

function periodLabel(filters: AnalyticsFilters, recentWindowLimit: number) {
  if (filters.started_after || filters.started_before) {
    const after = filters.started_after ? formatDate(filters.started_after) : "start";
    const before = filters.started_before ? formatDate(filters.started_before) : "now";
    return `${after} - ${before}`;
  }
  return `Last ${recentWindowLimit} conversations`;
}

function buildBreakdown(values: string[]): BreakdownItem[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value || "unknown", (counts.get(value || "unknown") ?? 0) + 1);
  return [...counts.entries()].sort((left, right) => right[1] - left[1]).map(([label, value]) => ({ label, value }));
}

function isNumber(value: number | null): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function toDateInput(value: string | undefined) {
  if (!value) return "";
  return value.slice(0, 10);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

function normaliseQuestion(value: string) {
  return value.trim().replace(/\s+/g, " ").slice(0, 140);
}

function minutesSince(value: string) {
  return (Date.now() - new Date(value).getTime()) / 60_000;
}

function daysSince(value: string) {
  return Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
}

function formatRelativeTime(value: string | null) {
  if (!value) return "No activity recorded";
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatDate(value);
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
