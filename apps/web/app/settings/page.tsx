import { PlaceholderPage } from "../../components/placeholder-page";

export default function SettingsPage() {
  return (
    <PlaceholderPage
      eyebrow="Settings"
      title="The workspace control room"
      description="A placeholder for workspace identity, allowed domains, branding constraints, fallback contact, and operational preferences."
      primaryMetric="Controls"
      primaryMetricLabel="local placeholder state"
      focusItems={[
        "Workspace profile and client branding",
        "Future allowed domain controls",
        "Safe defaults for public chatbot behavior",
      ]}
    />
  );
}
