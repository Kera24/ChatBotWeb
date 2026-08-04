import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Info, X } from "lucide-react";

import type { ConversationCitation } from "../../lib/api/types";

type CitationChipListProps = {
  citations: ConversationCitation[];
  onSelectCitation: (citation: ConversationCitation) => void;
};

export function CitationChipList({ citations, onSelectCitation }: CitationChipListProps) {
  if (citations.length === 0) return <div className="citationEmpty"><Info size={14} aria-hidden="true" />No citations were returned for this answer.</div>;

  return (
    <div className="premiumCitationList" aria-label="Assistant citations">
      <div className="citationListHeader"><strong>Sources</strong><span>{citations.length} citation{citations.length === 1 ? "" : "s"}</span></div>
      {citations.map((citation) => (
        <button
          className="citationChip"
          type="button"
          key={citation.id}
          onClick={() => onSelectCitation(citation)}
          aria-label={`Open citation ${citation.citation_index}: ${citation.source_title}`}
        >
          <span>[{citation.citation_index}]</span>
          <strong>{citation.source_title}</strong>
          <small>{citation.source_type}{citation.page_number !== null ? ` - page ${citation.page_number}` : ""}</small>
        </button>
      ))}
    </div>
  );
}

export function CitationDrawer({ citation, onClose }: { citation: ConversationCitation | null; onClose: () => void }) {
  const reduceMotion = useReducedMotion();
  return (
    <AnimatePresence>
      {citation ? (
        <motion.div
          className="citationDrawerBackdrop"
          role="presentation"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={reduceMotion ? undefined : { opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0 }}
          onClick={onClose}
        >
          <motion.aside
            className="citationDrawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="conversation-citation-drawer-title"
            initial={reduceMotion ? false : { opacity: 0, x: 24 }}
            animate={reduceMotion ? undefined : { opacity: 1, x: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, x: 24 }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="citationDrawerHeader">
              <div>
                <p>Source reference</p>
                <h2 id="conversation-citation-drawer-title">[{citation.citation_index}] {citation.source_title}</h2>
              </div>
              <button className="chatIconButton" type="button" onClick={onClose} aria-label="Close citation details">
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <blockquote>{citation.quoted_text || "Citation text was not stored for this answer."}</blockquote>
            <dl className="citationFacts">
              <div><dt>Document</dt><dd>{citation.document_id}</dd></div>
              <div><dt>Version</dt><dd>{citation.document_version_id}</dd></div>
              <div><dt>Type</dt><dd>{citation.source_type}</dd></div>
              {citation.page_number !== null ? <div><dt>Page</dt><dd>{citation.page_number}</dd></div> : null}
              {citation.section_title ? <div><dt>Section</dt><dd>{citation.section_title}</dd></div> : null}
              {citation.similarity_score !== null ? <div><dt>Similarity</dt><dd>{Number(citation.similarity_score).toFixed(3)}</dd></div> : null}
            </dl>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
