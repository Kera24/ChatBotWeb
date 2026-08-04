"use client";

import { motion, useReducedMotion } from "framer-motion";

import type { ConversationSummary } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle } from "../assistants/assistant-management";
import { NoConversationsState, NoFilterResultsState } from "./conversation-empty-states";
import { ConversationArchivedNotice, ConversationsListHeader } from "./conversation-header";
import { ConversationFilters } from "./conversation-filters";
import { ConversationInbox } from "./conversation-list";
import { PaginationControls } from "./pagination-controls";

type ConversationsViewProps = {
  assistant: WidgetDetail;
  conversations: ConversationSummary[];
  filters: { status?: string; channel?: string; startedAfter?: string; startedBefore?: string };
  limit: number;
  offset: number;
  hasNext: boolean;
  hasActiveFilters: boolean;
};

export function ConversationsView({ assistant, conversations, filters, limit, offset, hasNext, hasActiveFilters }: ConversationsViewProps) {
  const reduceMotion = useReducedMotion();
  const lifecycle = assistantLifecycle(assistant);
  const periodLabel = periodLabelFor(filters, limit);
  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="conversationPage premiumConversationsPage" aria-labelledby="conversation-title" {...pageMotion}>
      <ConversationsListHeader assistant={assistant} visibleCount={conversations.length} periodLabel={periodLabel} />
      {lifecycle === "Archived" ? <ConversationArchivedNotice /> : null}
      <ConversationFilters
        status={filters.status}
        channel={filters.channel}
        limit={limit}
        assistantId={assistant.id}
        startedAfter={filters.startedAfter}
        startedBefore={filters.startedBefore}
      />

      {conversations.length === 0 ? (
        hasActiveFilters ? <NoFilterResultsState assistantId={assistant.id} /> : <NoConversationsState assistantId={assistant.id} />
      ) : (
        <motion.div
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={reduceMotion ? undefined : { opacity: 1 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <ConversationInbox conversations={conversations} assistantId={assistant.id} assistantLabel={assistant.display_name} />
        </motion.div>
      )}

      <PaginationControls basePath="/conversations" status={filters.status} channel={filters.channel} limit={limit} offset={offset} hasNext={hasNext} assistantId={assistant.id} />
    </motion.section>
  );
}

function periodLabelFor(filters: { startedAfter?: string; startedBefore?: string }, limit: number) {
  if (filters.startedAfter || filters.startedBefore) {
    return `Started ${filters.startedAfter ?? "the beginning"} to ${filters.startedBefore ?? "now"}`;
  }
  return `Most recent conversations, up to ${limit} per page`;
}
