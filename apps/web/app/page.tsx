import { PlaceholderPage } from "../components/placeholder-page";

export default function OverviewPage() {
  return (
    <PlaceholderPage
      eyebrow="Overview"
      title="The workspace pulse"
      description="A foundation view for client admins to understand knowledge health, chatbot readiness, and trust signals before real data is connected."
      primaryMetric="Foundation"
      primaryMetricLabel="static dashboard shell"
      focusItems={[
        "Workspace readiness summary",
        "Knowledge health indicators",
        "Source-grounded answer quality signals",
      ]}
    />
  );
}
