import { Ban, CheckCircle2, Clock3, type LucideIcon } from "lucide-react";

const STATUS_TONE: Record<string, string> = {
  active: "success",
  inactive: "neutral",
};

const STATUS_ICON: Record<string, LucideIcon> = {
  active: CheckCircle2,
  inactive: Ban,
};

export function MemberStatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? "warning";
  const Icon = STATUS_ICON[status] ?? Clock3;
  const label = status.replace(/_/g, " ");
  return (
    <span className={`memberStatusBadge tone-${tone}`} aria-label={`Status: ${label}`}>
      <Icon size={13} aria-hidden="true" />
      {label}
    </span>
  );
}
