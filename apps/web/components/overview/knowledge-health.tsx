import { ArrowRight, FileWarning } from "lucide-react";
import Link from "next/link";

import type { DocumentRecord } from "../../lib/api/documents";
import type { WidgetDetail } from "../../lib/api/widgets";

export function KnowledgeHealth({ documents, assistants }: { documents: DocumentRecord[]; assistants: WidgetDetail[] }) {
  const ready = documents.filter((document) => document.status === "ready").length;
  const processing = documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const failed = documents.filter((document) => document.status === "failed").length;
  const recentUploads = [...documents].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5);
  const latestUpdate = documents.length === 0 ? null : documents.reduce((latest, document) => (new Date(document.updated_at).getTime() > new Date(latest).getTime() ? document.updated_at : latest), documents[0].updated_at);
  const assistantsWithoutKnowledge = assistants.filter((assistant) => (assistant.draft?.configuration.knowledge_scope_json.length ?? 0) === 0);

  return (
    <section className="overviewPanel knowledgeHealthPanel" aria-labelledby="knowledge-health-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Knowledge health</p>
          <h3 id="knowledge-health-title">Document lifecycle</h3>
        </div>
        <Link className="smallButton" href="/knowledge">Open knowledge base<ArrowRight size={13} aria-hidden="true" /></Link>
      </div>

      <dl className="overviewFacts compactFacts">
        <div><dt>Total documents</dt><dd>{documents.length}</dd></div>
        <div><dt>Ready</dt><dd>{ready}</dd></div>
        <div><dt>Processing</dt><dd>{processing}</dd></div>
        <div><dt>Failed</dt><dd>{failed}</dd></div>
        <div><dt>Latest update</dt><dd>{latestUpdate ? formatDate(latestUpdate) : "None yet"}</dd></div>
      </dl>

      {recentUploads.length > 0 ? (
        <div className="knowledgeRecentUploads">
          <h4>Recent uploads</h4>
          <ul>
            {recentUploads.map((document) => (
              <li key={document.id}>
                <span>{document.title}</span>
                <span className="reviewFilterNote">{formatEnum(document.status)} · {formatDate(document.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {assistantsWithoutKnowledge.length > 0 ? (
        <div className="knowledgeGapAssistants">
          <h4><FileWarning size={13} aria-hidden="true" />Assistants with no knowledge</h4>
          <ul>
            {assistantsWithoutKnowledge.map((assistant) => (
              <li key={assistant.id}>
                <span>{assistant.display_name}</span>
                <Link href={`/knowledge?assistant=${assistant.id}`}>Add knowledge<ArrowRight size={12} aria-hidden="true" /></Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

function formatEnum(value: string) {
  return value.replace(/_/g, " ");
}
