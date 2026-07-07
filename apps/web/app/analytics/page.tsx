import { PlaceholderPage } from "../../components/placeholder-page";

export default function AnalyticsPage() {
  return (
    <PlaceholderPage
      eyebrow="Analytics"
      title="Questions reveal what people need"
      description="A placeholder for conversations, unanswered questions, common topics, feedback, cost signals, and retrieval-quality review."
      primaryMetric="Signals"
      primaryMetricLabel="static preview only"
      focusItems={[
        "Unanswered and low-confidence questions",
        "Conversation and usage trends",
        "Documents used and estimated AI cost",
      ]}
    />
  );
}
