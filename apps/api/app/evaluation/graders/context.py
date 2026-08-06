"""GradingContext: the sanitised, assistant-scoped input handed to a
grader. Assembled once per result by engine.py from data already persisted
on the EvaluationResult/EvaluationCase (never re-fetched from live
production data), so a grader only ever sees exactly what the assistant
itself was authorised to use - the same evidence, not the live system
prompt, not credentials, not other tenants' data (Section 3's explicit
"evidence supplied to graders must be authorised and assistant-scoped" and
"no secrets or internal system prompts passed to graders" requirements).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str  # the citation_index as a string, e.g. "1" - matches what the answer's inline citations refer to
    chunk_id: str
    document_title: str
    content: str


@dataclass(frozen=True)
class GradingContext:
    question: str
    answer: str
    answer_state: str
    category: str
    expected_answerability: str
    reference_answer: str | None
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)

    def evidence_block(self) -> str:
        if not self.evidence:
            return "(no evidence was retrieved for this answer)"
        return "\n\n".join(f"[{item.evidence_id}] {item.document_title}\n{item.content}" for item in self.evidence)
