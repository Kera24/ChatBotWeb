import { ChatbotClient } from "../../components/chatbot/chatbot-client";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function ChatbotPage() {
  const session = await requireDashboardSession();

  return <ChatbotClient session={session} />;
}
