import { Activity, ExternalLink, FileText, Gauge, Layers, ShieldAlert } from "lucide-react";
import Link from "next/link";

import type { ConversationDetail, ConversationMessage } from "../../lib/api/types";
import { ConversationStatusBadge } from "./conversation-status-badge";

const FLAGGED_STATES = new Set(["fallback", "low_confidence", "failed"]);

export type ConversationQualitySummary = {
  messageCount: number;
  assistantMessageCount: number;
  citationTotal: number;
  sourceCount: number;
  totalTokens: number | null;
  averageLatency: number | null;
  lastAnswerState: string | null;
  lastProvider: string | null;
  lastModel: string | null;
  flaggedMessages: ConversationMessage[];
};

export function summarizeConversationQuality(conversation: ConversationDetail): ConversationQualitySummary {
  const assistantMessages = conversation.messages.filter((message) => message.role === "assistant");
  const citationIds = new Set<string>();
  let citationTotal = 0;
  for (const message of assistantMessages) {
    citationTotal += message.citations.length;
    for (const citation of message.citations) citationIds.add(citation.document_id);
  }
  const tokens = assistantMessages.map((message) => message.total_tokens).filter((value): value is number => typeof value === "number");
  const latencies = assistantMessages.map((message) => message.latency_ms).filter((value): value is number => typeof value === "number");
  const lastAssistantMessage = assistantMessages[assistantMessages.length - 1] ?? null;
  const flaggedMessages = assistantMessages.filter((message) => message.answer_state && FLAGGED_STATES.has(message.answer_state));

  return {
    messageCount: conversation.messages.length,
    assistantMessageCount: assistantMessages.length,
    citationTotal,
    sourceCount: citationIds.size,
    totalTokens: tokens.length === 0 ? null : tokens.reduce((sum, value) => sum + value, 0),
    averageLatency: latencies.length === 0 ? null : Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length),
    lastAnswerState: lastAssistantMessage?.answer_state ?? null,
    lastProvider: lastAssistantMessage?.provider_key ?? null,
    lastModel: lastAssistantMessage?.model_key ?? null,
    flaggedMessages,
  };
}

export function ConversationQualityPanel({ summary, assistantId }: { summary: ConversationQualitySummary; assistantId: string }) {
  return (
    <aside className="conversationQualityPanel" aria-labelledby="conversation-quality-title">
      <div className="conversationQualityHeader">
        <p className="sectionKicker">Review signals</p>
        <h3 id="conversation-quality-title">Quality &amp; metadata</h3>
      </div>

      <dl className="chatSideFacts conversationQualityFacts">
        <div>
          <dt>Last answer state</dt>
          <dd>{summary.lastAnswerState ? <ConversationStatusBadge status={summary.lastAnswerState} answerState /> : "No sample"}</dd>
        </div>
        <div>
          <dt>Assistant messages</dt>
          <dd>{summary.assistantMessageCount}</dd>
        </div>
        <div>
          <dt>Citations</dt>
          <dd>{summary.citationTotal}</dd>
        </div>
        <div>
          <dt>Unique sources</dt>
          <dd>{summary.sourceCount}</dd>
        </div>
        <div>
          <dt>Average latency</dt>
          <dd>{summary.averageLatency === null ? "No sample" : `${summary.averageLatency} ms`}</dd>
        </div>
        <div>
          <dt>Total tokens</dt>
          <dd>{summary.totalTokens === null ? "No sample" : summary.totalTokens}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{summary.lastProvider ?? "No sample"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{summary.lastModel ?? "No sample"}</dd>
        </div>
      </dl>

      <div className="conversationQualityGaps">
        <p className="conversationQualityGapsHeading"><ShieldAlert size={15} aria-hidden="true" />Knowledge gap items</p>
        {summary.flaggedMessages.length === 0 ? (
          <p className="conversationFilterNote">No fallback, low-confidence, or failed responses in this conversation.</p>
        ) : (
          <ul className="conversationQualityGapList">
            {summary.flaggedMessages.map((message) => (
              <li key={message.id}>
                <ConversationStatusBadge status={message.answer_state} answerState />
                <Link href={`/review/unanswered/${message.id}?assistant=${assistantId}`}>
                  Open review record
                  <ExternalLink size={13} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="conversationQualityLinks">
        <Link href={`/review/unanswered?assistant=${assistantId}`}><Layers size={15} aria-hidden="true" />Knowledge gap queue</Link>
        <Link href={`/analytics?assistant=${assistantId}`}><Activity size={15} aria-hidden="true" />Assistant analytics</Link>
        <Link href={`/knowledge?assistant=${assistantId}`}><FileText size={15} aria-hidden="true" />Knowledge base</Link>
      </div>

      <p className="conversationQualityCaveat"><Gauge size={13} aria-hidden="true" />Review status for individual flagged messages is available on their linked review record, not fetched here to avoid extra requests.</p>
    </aside>
  );
}
