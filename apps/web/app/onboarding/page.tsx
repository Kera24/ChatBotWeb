import { AssistantOnboardingWizard } from "../../components/onboarding/assistant-onboarding-wizard";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const session = await requireDashboardSession({ requireOnboarding: false });
  return <AssistantOnboardingWizard session={session} />;
}