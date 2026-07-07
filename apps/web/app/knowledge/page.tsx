import { PlaceholderPage } from "../../components/placeholder-page";

export default function KnowledgePage() {
  return (
    <PlaceholderPage
      eyebrow="Knowledge Base"
      title="Where institutional memory becomes usable"
      description="A placeholder for upload, document lifecycle, processing status, source visibility, and future tenant-scoped knowledge controls."
      primaryMetric="Sources"
      primaryMetricLabel="awaiting database foundation"
      focusItems={[
        "Document status and processing states",
        "FAQ and source management",
        "Clear exclusion of archived or expired knowledge",
      ]}
    />
  );
}
