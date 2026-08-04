import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";
import { NoAssistantSelectedState } from "../../../components/review/review-empty-states";
import { summarizeSampleSignals } from "../../../components/review/review-metrics";
import type { ReviewMetricsData } from "../../../components/review/review-metrics";
import { ReviewQueueView } from "../../../components/review/review-queue-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { listUnansweredReviewItems } from "../../../lib/api/review";
import type { ReviewListMeta, ReviewItem } from "../../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { getWidgetDetail } from "../../../lib/api/widgets";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

type ReviewPageProps = {
  searchParams: Promise<{
    answer_state?: string;
    review_status?: string;
    channel?: string;
    created_after?: string;
    created_before?: string;
    limit?: string;
    offset?: string;
    assistant?: string;
  }>;
};

export default async function ReviewQueuePage({ searchParams }: ReviewPageProps) {
  const params = await searchParams;
  const limit = clampNumber(params.limit, 20, 1, 50);
  const offset = clampNumber(params.offset, 0, 0, 10_000);
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const assistantId = params.assistant;
  const filters = {
    answer_state: params.answer_state,
    review_status: params.review_status,
    channel: params.channel,
    created_after: params.created_after,
    created_before: params.created_before,
  };

  const [result, assistantResult, metricsResult] = await Promise.all([
    loadReviewItems(session, { assistantId, ...filters, limit, offset }),
    loadAssistant(session, assistantId),
    loadReviewMetrics(session, assistantId),
  ]);

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/review/unanswered?assistant=${assistantId}`} />;
  }
  if (!assistantResult.ok) {
    if (assistantResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(assistantResult.error)} retryHref={`/review/unanswered?assistant=${assistantId}`} />;
  }
  if (!metricsResult.ok) {
    if (metricsResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(metricsResult.error)} retryHref={`/review/unanswered?assistant=${assistantId}`} />;
  }

  const items = result.data;
  const total = result.meta.total ?? items.length;
  const hasActiveFilters = Boolean(params.answer_state || params.review_status || params.channel || params.created_after || params.created_before);
  const sample = summarizeSampleSignals(items);

  return (
    <ReviewQueueView
      assistant={assistantResult.data}
      items={items}
      metrics={metricsResult.data}
      sample={sample}
      filters={{
        answerState: params.answer_state,
        reviewStatus: params.review_status,
        channel: params.channel,
        createdAfter: params.created_after,
        createdBefore: params.created_before,
      }}
      limit={limit}
      offset={offset}
      total={total}
      hasNext={offset + items.length < total}
      hasActiveFilters={hasActiveFilters}
    />
  );
}

function clampNumber(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

async function loadReviewItems(
  session: DevelopmentDashboardSession,
  params: { assistantId: string; answer_state?: string; review_status?: string; channel?: string; created_after?: string; created_before?: string; limit: number; offset: number },
): Promise<{ ok: true; data: ReviewItem[]; meta: ReviewListMeta } | { ok: false; error: DashboardApiError }> {
  try {
    const response = await listUnansweredReviewItems(session, params);
    return { ok: true, data: response.data, meta: response.meta ?? { limit: params.limit, offset: params.offset, count: response.data.length, total: response.data.length } };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false, error };
    return { ok: false, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
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

async function loadReviewMetrics(
  session: DevelopmentDashboardSession,
  assistantId: string,
): Promise<{ ok: true; data: ReviewMetricsData } | { ok: false; error: DashboardApiError }> {
  try {
    const [open, reviewed, dismissed, knowledgeGap, fallback, lowConfidence, failed] = await Promise.all([
      reviewCount(session, assistantId, { review_status: "open" }),
      reviewCount(session, assistantId, { review_status: "reviewed" }),
      reviewCount(session, assistantId, { review_status: "dismissed" }),
      reviewCount(session, assistantId, { review_status: "knowledge_gap" }),
      reviewCount(session, assistantId, { answer_state: "fallback" }),
      reviewCount(session, assistantId, { answer_state: "low_confidence" }),
      reviewCount(session, assistantId, { answer_state: "failed" }),
    ]);
    return {
      ok: true,
      data: {
        pending: open,
        resolved: reviewed + dismissed + knowledgeGap,
        needsKnowledge: knowledgeGap,
        fallbacks: fallback,
        lowConfidence,
        failed,
      },
    };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false, error };
    return { ok: false, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function reviewCount(session: DevelopmentDashboardSession, assistantId: string, filter: { review_status?: string; answer_state?: string }) {
  const response = await listUnansweredReviewItems(session, { assistantId, ...filter, limit: 1, offset: 0 });
  return response.meta?.total ?? response.data.length;
}
