import Link from "next/link";

import { EmptyState, AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../../components/conversations/state-panels";
import { ReviewPaginationControls } from "../../../components/review/review-pagination-controls";
import { ReviewFilters } from "../../../components/review/review-filters";
import { ReviewList } from "../../../components/review/review-list";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { listUnansweredReviewItems } from "../../../lib/api/review";
import type { ReviewListMeta, ReviewItem } from "../../../lib/api/types";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../../lib/auth/development-session";

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
  }>;
};

export default async function ReviewQueuePage({ searchParams }: ReviewPageProps) {
  const params = await searchParams;
  const limit = clampNumber(params.limit, 20, 1, 50);
  const offset = clampNumber(params.offset, 0, 0, 10_000);
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadReviewItems(tenant.session, {
    answer_state: params.answer_state,
    review_status: params.review_status,
    channel: params.channel,
    created_after: params.created_after,
    created_before: params.created_before,
    limit,
    offset,
  });

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/review/unanswered" />;
  }

  const items = result.data;
  const total = result.meta.total ?? items.length;

  return (
    <section className="conversationPage reviewQueuePage" aria-labelledby="review-title">
      <div className="conversationHero reviewHero">
        <div>
          <p className="eyebrow">Knowledge gaps</p>
          <h2 id="review-title">Answers that need a human look</h2>
          <p>Review fallback, failed, and low-confidence answers so missing knowledge becomes visible without inventing remediation.</p>
        </div>
        <div className="conversationHeroAside reviewHeroAside">
          <strong>{total}</strong>
          <span>flagged in this filter</span>
        </div>
      </div>

      <div className="conversationToolbar">
        <ReviewFilters
          answerState={params.answer_state}
          reviewStatus={params.review_status}
          channel={params.channel}
          createdAfter={params.created_after}
          createdBefore={params.created_before}
          limit={limit}
        />
        <Link className="actionButton" href="/review/unanswered" aria-label="Refresh review queue">Refresh</Link>
      </div>

      {items.length === 0 ? <EmptyState /> : <ReviewList items={items} />}

      <ReviewPaginationControls
        basePath="/review/unanswered"
        answerState={params.answer_state}
        reviewStatus={params.review_status}
        channel={params.channel}
        createdAfter={params.created_after}
        createdBefore={params.created_before}
        limit={limit}
        offset={offset}
        hasNext={offset + items.length < total}
      />
    </section>
  );
}

function clampNumber(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

async function loadReviewItems(
  session: DevelopmentDashboardSession,
  params: { answer_state?: string; review_status?: string; channel?: string; created_after?: string; created_before?: string; limit: number; offset: number },
): Promise<{ ok: true; data: ReviewItem[]; meta: ReviewListMeta } | { ok: false; error: DashboardApiError }> {
  try {
    const response = await listUnansweredReviewItems(session, params);
    return { ok: true, data: response.data, meta: response.meta ?? { limit: params.limit, offset: params.offset, count: response.data.length, total: response.data.length } };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false, error };
    return { ok: false, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
