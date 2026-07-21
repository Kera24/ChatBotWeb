import type { ConversationCitation } from "../../lib/api/types";

type CitationListProps = {
  citations: ConversationCitation[];
};

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div className="citationList" aria-label="Assistant citations">
      {citations.map((citation) => (
        <article className="citationCard" key={citation.id}>
          <div>
            <strong>[{citation.citation_index}] {citation.source_title}</strong>
            <p>{citation.quoted_text || "Citation text was not stored."}</p>
          </div>
          <dl>
            <div>
              <dt>Type</dt>
              <dd>{citation.source_type}</dd>
            </div>
            {citation.page_number !== null ? (
              <div>
                <dt>Page</dt>
                <dd>{citation.page_number}</dd>
              </div>
            ) : null}
            {citation.section_title ? (
              <div>
                <dt>Section</dt>
                <dd>{citation.section_title}</dd>
              </div>
            ) : null}
            {citation.similarity_score !== null ? (
              <div>
                <dt>Similarity</dt>
                <dd>{Number(citation.similarity_score).toFixed(3)}</dd>
              </div>
            ) : null}
          </dl>
        </article>
      ))}
    </div>
  );
}
