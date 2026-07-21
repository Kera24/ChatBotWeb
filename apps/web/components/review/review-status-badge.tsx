const labelMap: Record<string, string> = {
  open: "Open",
  reviewed: "Reviewed",
  dismissed: "Dismissed",
  knowledge_gap: "Knowledge gap",
};

export function ReviewStatusBadge({ status }: { status: string | null | undefined }) {
  const key = status ?? "open";
  const label = labelMap[key] ?? key.replace(/_/g, " ");
  return (
    <span className={`reviewStatusBadge review-${key}`}>
      <span className="statusBadgeDot" aria-hidden="true" />
      {label}
    </span>
  );
}
