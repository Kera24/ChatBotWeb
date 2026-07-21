import Link from "next/link";

export function LoadingState({ title = "Loading conversations" }: { title?: string }) {
  return (
    <section className="statePanel" aria-live="polite" aria-busy="true">
      <p className="sectionKicker">Loading</p>
      <h2>{title}</h2>
      <p>The dashboard is asking the tenant-scoped API for the latest conversation history.</p>
    </section>
  );
}

export function EmptyState() {
  return (
    <section className="statePanel">
      <p className="sectionKicker">No conversations yet</p>
      <h2>The room is quiet</h2>
      <p>Once the internal RAG endpoint is used, conversations for this workspace will appear here with messages and citations.</p>
    </section>
  );
}

export function MissingTenantConfiguration({ missing, invalid = [] }: { missing: string[]; invalid?: string[] }) {
  return (
    <section className="statePanel urgentState">
      <p className="sectionKicker">Development setup required</p>
      <h2>Tenant context is missing</h2>
      <p>Add these safe local variables before loading conversation history:</p>
      {missing.length > 0 ? (
        <ul aria-label="Missing development variables">
          {missing.map((item) => (
            <li key={item}><code>{item}</code></li>
          ))}
        </ul>
      ) : null}
      {invalid.length > 0 ? (
        <>
          <p>Correct these invalid local variables:</p>
          <ul aria-label="Invalid development variables">
            {invalid.map((item) => (
              <li key={item}><code>{item}</code></li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

export function AccessDeniedState() {
  return (
    <section className="statePanel urgentState">
      <p className="sectionKicker">Access denied</p>
      <h2>This development user cannot view this workspace</h2>
      <p>Check the temporary user email, role, organisation ID, and workspace ID.</p>
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
