import { ChatbotClient } from "../../components/chatbot/chatbot-client";
import { MissingTenantConfiguration } from "../../components/conversations/state-panels";
import { getDevelopmentDashboardSession } from "../../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default function ChatbotPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  return <ChatbotClient session={tenant.session} />;
}
