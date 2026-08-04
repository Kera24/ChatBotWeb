"use client";

import { motion, useReducedMotion } from "framer-motion";

import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle } from "../assistants/assistant-management";
import { NoFilterResultsState, NoReviewItemsState } from "./review-empty-states";
import { ReviewFilters } from "./review-filters";
import { ReviewArchivedNotice, ReviewQueueHeader } from "./review-header";
import { ReviewList } from "./review-list";
import type { ReviewMetricsData, ReviewSampleSignals } from "./review-metrics";
import { ReviewMetrics } from "./review-metrics";
import { ReviewPaginationControls } from "./review-pagination-controls";

type ReviewQueueViewProps = {
  assistant: WidgetDetail;
  items: ReviewItem[];
  metrics: ReviewMetricsData;
  sample: ReviewSampleSignals;
  filters: { answerState?: string; reviewStatus?: string; channel?: string; createdAfter?: string; createdBefore?: string };
  limit: number;
  offset: number;
  total: number;
  hasNext: boolean;
  hasActiveFilters: boolean;
};

export function ReviewQueueView({ assistant, items, metrics, sample, filters, limit, offset, total, hasNext, hasActiveFilters }: ReviewQueueViewProps) {
  const reduceMotion = useReducedMotion();
  const lifecycle = assistantLifecycle(assistant);
  const periodLabel = periodLabelFor(filters);
  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="conversationPage reviewQueuePage premiumReviewQueuePage" aria-labelledby="review-title" {...pageMotion}>
      <ReviewQueueHeader assistant={assistant} pending={metrics.pending} resolved={metrics.resolved} totalInFilter={total} periodLabel={periodLabel} />
      {lifecycle === "Archived" ? <ReviewArchivedNotice /> : null}

      <ReviewMetrics data={metrics} sample={sample} />

      <ReviewFilters
        answerState={filters.answerState}
        reviewStatus={filters.reviewStatus}
        channel={filters.channel}
        createdAfter={filters.createdAfter}
        createdBefore={filters.createdBefore}
        limit={limit}
        assistantId={assistant.id}
      />

      {items.length === 0 ? (
        hasActiveFilters ? <NoFilterResultsState assistantId={assistant.id} /> : <NoReviewItemsState assistantId={assistant.id} />
      ) : (
        <motion.div
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={reduceMotion ? undefined : { opacity: 1 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <ReviewList items={items} assistantId={assistant.id} assistantLabel={assistant.display_name} />
        </motion.div>
      )}

      <ReviewPaginationControls
        basePath="/review/unanswered"
        answerState={filters.answerState}
        reviewStatus={filters.reviewStatus}
        channel={filters.channel}
        createdAfter={filters.createdAfter}
        createdBefore={filters.createdBefore}
        limit={limit}
        offset={offset}
        total={total}
        hasNext={hasNext}
        assistantId={assistant.id}
      />
    </motion.section>
  );
}

function periodLabelFor(filters: { createdAfter?: string; createdBefore?: string }) {
  if (filters.createdAfter || filters.createdBefore) {
    return `Created ${filters.createdAfter ?? "the beginning"} to ${filters.createdBefore ?? "now"}`;
  }
  return "Most recent flagged answers";
}
