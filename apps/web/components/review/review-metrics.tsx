import type { ReviewItem } from "../../lib/api/types";

export type ReviewMetricsData = {
  pending: number;
  resolved: number;
  needsKnowledge: number;
  fallbacks: number;
  lowConfidence: number;
  failed: number;
};

export type ReviewSampleSignals = {
  reviewedToday: number;
  averageReviewAgeLabel: string;
  sampleSize: number;
};

export function summarizeSampleSignals(items: ReviewItem[]): ReviewSampleSignals {
  const today = new Date().toDateString();
  const reviewedToday = items.filter((item) => item.reviewed_at && new Date(item.reviewed_at).toDateString() === today).length;
  const ages = items
    .filter((item): item is ReviewItem & { reviewed_at: string } => Boolean(item.reviewed_at))
    .map((item) => new Date(item.reviewed_at).getTime() - new Date(item.created_at).getTime())
    .filter((value) => Number.isFinite(value) && value >= 0);
  const averageReviewAgeLabel = ages.length === 0 ? "No sample" : formatDuration(ages.reduce((sum, value) => sum + value, 0) / ages.length);

  return { reviewedToday, averageReviewAgeLabel, sampleSize: items.length };
}

function formatDuration(ms: number) {
  const minutes = Math.round(ms / 60_000);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hr`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"}`;
}

export function ReviewMetrics({ data, sample }: { data: ReviewMetricsData; sample: ReviewSampleSignals }) {
  const cards = [
    { key: "pending", label: "Pending", value: String(data.pending), detail: "Open items awaiting review, all time." },
    { key: "resolved", label: "Resolved", value: String(data.resolved), detail: "Reviewed, dismissed, or confirmed knowledge gaps, all time." },
    { key: "needs-knowledge", label: "Needs knowledge", value: String(data.needsKnowledge), detail: "Confirmed knowledge gaps, all time." },
    { key: "fallbacks", label: "Fallbacks", value: String(data.fallbacks), detail: "Fallback answers, all time." },
    { key: "low-confidence", label: "Low confidence", value: String(data.lowConfidence), detail: "Low-confidence answers, all time." },
    { key: "failed", label: "Failed answers", value: String(data.failed), detail: "Failed answers, all time." },
    { key: "reviewed-today", label: "Reviewed today", value: String(sample.reviewedToday), detail: `From the ${sample.sampleSize} item${sample.sampleSize === 1 ? "" : "s"} on this page.` },
    { key: "average-age", label: "Average review age", value: sample.averageReviewAgeLabel, detail: `From reviewed items on this page.` },
  ];

  return (
    <section className="reviewMetricGrid" aria-label="Review queue summary metrics">
      {cards.map((card) => (
        <article className="reviewMetricCard" key={card.key}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <p>{card.detail}</p>
        </article>
      ))}
    </section>
  );
}
