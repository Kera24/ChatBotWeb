import { ChatbotClient } from "../../components/chatbot/chatbot-client";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type ChatbotPageProps = { searchParams: Promise<{ assistant?: string }> };

export default async function ChatbotPage({ searchParams }: ChatbotPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <ChatbotClient session={session} assistantId="" missingAssistant />;

  return <ChatbotClient session={session} assistantId={params.assistant} />;
}