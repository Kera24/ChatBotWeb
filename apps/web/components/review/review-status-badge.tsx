import { AlertTriangle, Ban, CheckCircle2, Clock3, type LucideIcon } from "lucide-react";

const labelMap: Record<string, string> = {
  open: "Open",
  reviewed: "Reviewed",
  dismissed: "Dismissed",
  knowledge_gap: "Knowledge gap",
};

const toneMap: Record<string, string> = {
  open: "info",
  reviewed: "success",
  dismissed: "neutral",
  knowledge_gap: "warning",
};

const iconMap: Record<string, LucideIcon> = {
  info: Clock3,
  success: CheckCircle2,
  neutral: Ban,
  warning: AlertTriangle,
};

export function ReviewStatusBadge({ status }: { status: string | null | undefined }) {
  const key = status ?? "open";
  const label = labelMap[key] ?? key.replace(/_/g, " ");
  const tone = toneMap[key] ?? "neutral";
  const Icon = iconMap[tone];

  return (
    <span className={`reviewStatusPill tone-${tone}`} aria-label={`Review status: ${label}`}>
      <Icon size={13} aria-hidden="true" />
      {label}
    </span>
  );
}
