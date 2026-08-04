import { AlertTriangle, CheckCircle2, Circle, Clock3, XCircle, type LucideIcon } from "lucide-react";

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

const answerToneMap: Record<string, string> = {
  answered: "answered",
  fallback: "fallback",
  low_confidence: "low",
  failed: "failed",
  pending: "neutral",
};

const answerIconMap: Record<string, LucideIcon> = {
  answered: CheckCircle2,
  fallback: AlertTriangle,
  low: AlertTriangle,
  failed: XCircle,
  neutral: Clock3,
};

const conversationToneMap: Record<string, string> = {
  active: "info",
  completed: "success",
  abandoned: "warning",
  archived: "neutral",
};

export function ConversationStatusBadge({ status, answerState = false }: ConversationStatusBadgeProps) {
  const key = status ?? "pending";
  const label = labelMap[key] ?? key.replace(/_/g, " ");

  if (answerState) {
    const tone = answerToneMap[key] ?? "neutral";
    const Icon = answerIconMap[tone] ?? Clock3;
    return (
      <span className={`answerStateBadge state-${tone}`} aria-label={`Answer state: ${label}`}>
        <Icon size={13} aria-hidden="true" />
        {label}
      </span>
    );
  }

  const tone = conversationToneMap[key] ?? "neutral";
  return (
    <span className={`conversationStatusPill tone-${tone}`} aria-label={`Status: ${label}`}>
      <Circle className="conversationStatusDot" size={8} aria-hidden="true" fill="currentColor" />
      {label}
    </span>
  );
}
