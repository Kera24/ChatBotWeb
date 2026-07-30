import { describe, expect, it, vi } from "vitest";

import { answerChatbotQuestion } from "./chatbot";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-abc",
  workspaceId: "workspace-def",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function mockFetch() {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: { conversation_id: "conversation-1" }, meta: {} }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("chatbot API helper", () => {
  it("calls the workspace RAG answer endpoint with tenant scope", async () => {
    const mock = mockFetch();

    await answerChatbotQuestion(session, { query: "What is indexed?" });

    const url = new URL(String(mock.mock.calls[0][0]));
    const init = mock.mock.calls[0][1] as RequestInit;
    expect(url.pathname).toBe("/api/v1/workspaces/workspace-def/rag/answer");
    expect(url.searchParams.get("organisation_id")).toBe("org-abc");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ query: "What is indexed?" });
  });

  it("reuses the returned conversation when provided", async () => {
    const mock = mockFetch();

    await answerChatbotQuestion(session, { query: "Continue", conversationId: "conversation-123" });

    const init = mock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      query: "Continue",
      conversation_id: "conversation-123",
    });
  });
});
