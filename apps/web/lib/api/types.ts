export type ApiEnvelope<TData, TMeta = Record<string, unknown>> = {
  success: boolean;
  data: TData;
  meta?: TMeta;
};

export type ConversationStatus = "active" | "completed" | "abandoned" | "archived";
export type ConversationChannel = "dashboard_test" | "widget" | "api" | "future_integration";
export type MessageRole = "system" | "user" | "assistant" | "tool";
export type AnswerState = "answered" | "low_confidence" | "fallback" | "failed" | "pending";

export type ConversationSummary = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  channel: ConversationChannel | string;
  status: ConversationStatus | string;
  title: string | null;
  started_at: string;
  last_message_at: string | null;
  ended_at: string | null;
  message_count: number;
  last_message_preview: string | null;
  metadata: Record<string, unknown> | null;
};

export type ConversationCitation = {
  id: string;
  citation_index: number;
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  similarity_score: string | number | null;
  source_title: string;
  source_type: string;
  page_number: number | null;
  section_title: string | null;
  quoted_text: string | null;
  created_at: string;
};

export type ConversationMessage = {
  id: string;
  role: MessageRole | string;
  content: string;
  sequence_number: number;
  answer_state: AnswerState | string | null;
  model_key: string | null;
  provider_key: string | null;
  provider_model_name: string | null;
  prompt_key: string | null;
  prompt_version: number | null;
  prompt_hash: string | null;
  execution_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost: string | number | null;
  latency_ms: number | null;
  finish_reason: string | null;
  error_code: string | null;
  created_at: string;
  citations: ConversationCitation[];
};

export type ConversationDetail = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  channel: ConversationChannel | string;
  status: ConversationStatus | string;
  title: string | null;
  started_at: string;
  last_message_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown> | null;
  messages: ConversationMessage[];
};

export type ConversationListMeta = {
  limit: number;
  offset: number;
};

export type ConversationListParams = {
  status?: string;
  channel?: string;
  limit?: number;
  offset?: number;
};

export type ReviewStatus = "open" | "reviewed" | "dismissed" | "knowledge_gap";

export type ReviewItem = {
  conversation_id: string;
  assistant_message_id: string;
  user_question: string | null;
  assistant_answer: string;
  answer_state: AnswerState | string;
  error_code: string | null;
  channel: ConversationChannel | string;
  conversation_status: ConversationStatus | string;
  model_key: string | null;
  provider_key: string | null;
  prompt_key: string | null;
  prompt_version: number | null;
  citation_count: number;
  citations: ConversationCitation[];
  created_at: string;
  estimated_cost: string | number | null;
  latency_ms: number | null;
  review_status: ReviewStatus | string;
  reviewer_note: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

export type ReviewItemDetail = {
  item: ReviewItem;
  conversation_context: ConversationMessage[];
};

export type ReviewListMeta = {
  limit: number;
  offset: number;
  count: number;
  total: number;
};

export type ReviewListParams = {
  answer_state?: string;
  review_status?: string;
  channel?: string;
  created_after?: string;
  created_before?: string;
  limit?: number;
  offset?: number;
};
