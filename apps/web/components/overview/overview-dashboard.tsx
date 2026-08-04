"use client";

import { motion, useReducedMotion } from "framer-motion";

import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { assistantLifecycle } from "../assistants/assistant-management";
import { buildActionItems, ActionCentre } from "./action-centre";
import { AssistantPortfolio, buildAssistantPortfolio, NoAssistantsPortfolioState } from "./assistant-portfolio";
import { KnowledgeHealth } from "./knowledge-health";
import { OverviewHeader } from "./overview-header";
import { buildExecutiveMetrics, OverviewMetrics } from "./overview-metrics";
import { ZeroAssistantState } from "./overview-empty-states";
import { derivePlatformHealth, PlatformHealthPanel } from "./platform-health";
import { QualitySummary } from "./quality-summary";
import { QuickActions } from "./quick-actions";
import { buildRecentActivity, RecentActivity } from "./recent-activity";

const RECENT_CONVERSATION_WINDOW = 50;

type OverviewDashboardProps = {
  session: DevelopmentDashboardSession;
  data: OverviewData;
  assistants: WidgetDetail[];
  environment: string;
};

export function OverviewDashboard({ session, data, assistants, environment }: OverviewDashboardProps) {
  const reduceMotion = useReducedMotion();
  const health = derivePlatformHealth(data, assistants);
  const metrics = buildExecutiveMetrics(data, assistants, RECENT_CONVERSATION_WINDOW);
  const portfolio = buildAssistantPortfolio(assistants, data.conversations);
  const actionItems = buildActionItems(data, assistants, session);
  const activity = buildRecentActivity(data);
  const latestKnowledgeUpdate = latestDate(data.documents.map((document) => document.updated_at));
  const primaryAssistantId = pickPrimaryAssistant(assistants);

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="overviewPage premiumOverviewPage" aria-labelledby="overview-title" {...pageMotion}>
      <OverviewHeader
        workspaceName={session.workspaceName}
        organisationName={session.organisationName}
        environment={environment}
        role={session.role}
        health={health}
        latestKnowledgeUpdateLabel={latestKnowledgeUpdate ? formatDate(latestKnowledgeUpdate) : "none yet"}
        primaryAssistantId={primaryAssistantId}
      />

      {assistants.length === 0 ? (
        <ZeroAssistantState />
      ) : (
        <>
          <OverviewMetrics metrics={metrics} />

          <div className="overviewLayout">
            <PlatformHealthPanel health={health} />
            <ActionCentre items={actionItems} />
          </div>

          {portfolio.length === 0 ? <NoAssistantsPortfolioState /> : <AssistantPortfolio cards={portfolio} totalAssistants={assistants.length} />}

          <div className="overviewLayout">
            <KnowledgeHealth documents={data.documents} assistants={assistants} />
            <QualitySummary data={data} recentWindowLimit={RECENT_CONVERSATION_WINDOW} />
          </div>

          <QuickActions primaryAssistantId={primaryAssistantId} />

          <div className="overviewLayout">
            <RecentActivity items={activity} />
          </div>
        </>
      )}
    </motion.section>
  );
}

function pickPrimaryAssistant(assistants: WidgetDetail[]): string | null {
  if (assistants.length === 0) return null;
  const published = assistants.find((assistant) => assistantLifecycle(assistant) === "Published");
  return (published ?? assistants[0]).id;
}

function latestDate(values: string[]) {
  const timestamps = values.map((value) => new Date(value).getTime()).filter(Number.isFinite);
  if (timestamps.length === 0) return null;
  return new Date(Math.max(...timestamps)).toISOString();
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
