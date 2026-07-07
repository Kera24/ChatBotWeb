import { PlaceholderPage } from "../../components/placeholder-page";

export default function ChatbotPage() {
  return (
    <PlaceholderPage
      eyebrow="Chatbot"
      title="The public voice of the workspace"
      description="A placeholder for bot identity, welcome message, fallback contact, suggested questions, citations, and embed instructions."
      primaryMetric="Widget"
      primaryMetricLabel="not connected yet"
      focusItems={[
        "Brand-controlled chatbot settings",
        "Citation and low-confidence display states",
        "Future public widget configuration",
      ]}
    />
  );
}
