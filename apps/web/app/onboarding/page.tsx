import { AuthShell, OnboardingPanel } from "../../components/auth/auth-forms";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  await requireDashboardSession({ requireOnboarding: false });
  return <AuthShell title="Your workspace is ready" subtitle="Yoranix has created your organisation, default workspace, and owner access."><OnboardingPanel /></AuthShell>;
}
