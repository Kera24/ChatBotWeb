import { AssistantCreateForm } from "../../../components/assistants/assistant-create-form";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function NewAssistantPage() {
  const session = await requireDashboardSession();
  return <AssistantCreateForm session={session} />;
}
