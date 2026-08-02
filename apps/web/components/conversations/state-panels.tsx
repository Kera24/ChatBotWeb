import Link from "next/link";

export function LoadingState({ title = "Loading conversations" }: { title?: string }) {
  return (
    <section className="statePanel" aria-live="polite" aria-busy="true">
      <p className="sectionKicker">Loading</p>
      <h2>{title}</h2>
      <p>Yoranix is collecting the latest conversation history for this workspace.</p>
    </section>
  );
}

export function EmptyState() {
  return (
    <section className="statePanel">
      <p className="sectionKicker">No conversations yet</p>
      <h2>No conversations have been recorded</h2>
      <p>Once the assistant is tested or deployed, workspace conversations will appear here with messages and citations.</p>
    </section>
  );
}

export function MissingTenantConfiguration({ missing, invalid = [] }: { missing: string[]; invalid?: string[] }) {
  const issueCount = missing.length + invalid.length;

  return (
    <section className="statePanel urgentState">
      <p className="sectionKicker">Workspace unavailable</p>
      <h2>Workspace access is not ready</h2>
      <p>Yoranix could not establish a complete workspace context for this session. Ask an administrator to review workspace access before continuing.</p>
      {issueCount > 0 ? <p>{issueCount} configuration item{issueCount === 1 ? "" : "s"} need attention.</p> : null}
    </section>
  );
}

export function AccessDeniedState() {
  return (
    <section className="statePanel urgentState">
      <p className="sectionKicker">Access denied</p>
      <h2>You cannot view this workspace</h2>
      <p>Your current role does not have permission to access this workspace.</p>
    </section>
  );
}

export function ErrorState({ message, retryHref }: { message: string; retryHref: string }) {
  return (
    <section className="statePanel urgentState">
      <p className="sectionKicker">Conversation history unavailable</p>
      <h2>Something blocked this view</h2>
      <p>{message}</p>
      <Link className="actionButton" href={retryHref}>Retry</Link>
    </section>
  );
}
