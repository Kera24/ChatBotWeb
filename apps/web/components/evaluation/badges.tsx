export function EvaluationStatusBadge({ label, tone }: { label: string; tone: string }) {
  const normalised = label.replace(/_/g, " ");
  return (
    <span className={`statusBadge status-${tone}`} aria-label={normalised}>
      <span className="statusBadgeDot" aria-hidden="true" />
      <span>{normalised}</span>
    </span>
  );
}
