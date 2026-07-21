type ConversationStatusBadgeProps = {
  status: string | null | undefined;
  answerState?: boolean;
};

const labelMap: Record<string, string> = {
  active: "Active",
  completed: "Completed",
  abandoned: "Abandoned",
  archived: "Archived",
  answered: "Answered",
  low_confidence: "Low confidence",
  fallback: "Fallback",
  failed: "Failed",
  pending: "Pending",
};

export function ConversationStatusBadge({ status, answerState = false }: ConversationStatusBadgeProps) {
  const key = status ?? "pending";
  const label = labelMap[key] ?? key.replace(/_/g, " ");

  return (
    <span className={`statusBadge status-${key}`} data-answer-state={answerState}>
      <span className="statusBadgeDot" aria-hidden="true" />
      {label}
    </span>
  );
}
