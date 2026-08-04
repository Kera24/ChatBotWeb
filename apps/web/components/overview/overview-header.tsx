import { FileText, LayoutGrid, MessageSquare, PlusCircle, ShieldAlert } from "lucide-react";
import Link from "next/link";

import type { PlatformHealth } from "./platform-health";
import { PlatformHealthBadge } from "./platform-health";

export function OverviewHeader({
  workspaceName,
  organisationName,
  environment,
  role,
  health,
  latestKnowledgeUpdateLabel,
  primaryAssistantId,
}: {
  workspaceName: string;
  organisationName: string;
  environment: string;
  role: string;
  health: PlatformHealth;
  latestKnowledgeUpdateLabel: string;
  primaryAssistantId: string | null;
}) {
  return (
    <header className="premiumOverviewHero">
      <div className="overviewHeroMain">
        <div>
          <p className="eyebrow">Executive overview</p>
          <h2 id="overview-title">{workspaceName}</h2>
          <p>Operational command centre for {organisationName}&rsquo;s AI assistants, knowledge base, and answer quality.</p>
          <div className="overviewHeroMeta" aria-label="Workspace and platform summary">
            <PlatformHealthBadge health={health} />
            <span className="environmentBadge tone-neutral">{environment} environment</span>
            <span>{roleLabel(role)}</span>
            <span>Latest knowledge activity {latestKnowledgeUpdateLabel}</span>
          </div>
        </div>
      </div>
      <nav className="overviewQuickLinks" aria-label="Executive quick actions">
        <Link href="/assistants/new"><PlusCircle size={15} aria-hidden="true" />Create assistant</Link>
        {primaryAssistantId ? <Link href={`/knowledge?assistant=${primaryAssistantId}`}><FileText size={15} aria-hidden="true" />Upload knowledge</Link> : null}
        {primaryAssistantId ? <Link href={`/chatbot?assistant=${primaryAssistantId}`}><MessageSquare size={15} aria-hidden="true" />Open Playground</Link> : null}
        <Link href="/review/unanswered"><ShieldAlert size={15} aria-hidden="true" />Review knowledge gaps</Link>
        <Link href="/dashboard"><LayoutGrid size={15} aria-hidden="true" />Manage assistants</Link>
      </nav>
    </header>
  );
}

function roleLabel(role: string) {
  return role.replace(/_/g, " ");
}
