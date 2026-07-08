# Task: Evaluation and Quality Framework

## Task ID

TASK-016

## Linked epic/story

- EPIC-003

## Objective

Define a comprehensive engineering specification for evaluating RAG retrieval quality, answer quality, citation accuracy, fallback behaviour, tenant isolation, regressions, cost, latency, and future evaluation-tool integration.

This is an architecture-only task. Do not implement application code, database migrations, test runners, evaluation scripts, dashboards, runtime prompts, or external evaluation integrations in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/03_AI/01_RAG_Implementation_Standards.md`
- `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md`
- `planning/tasks/TASK-010-knowledge-platform-architecture.md`
- `planning/tasks/TASK-011-document-lifecycle-versioning.md`
- `planning/tasks/TASK-012-ingestion-pipeline-design.md`
- `planning/tasks/TASK-013-chunking-strategy.md`
- `planning/tasks/TASK-014-metadata-vector-schema.md`
- `planning/tasks/TASK-015-retrieval-prompt-flow.md`
- `docs/03_AI/01_RAG_Architecture.md`

## 1. Purpose of evaluation

The evaluation framework defines how the platform measures whether RAG answers are useful, grounded, safe, cited, tenant-isolated, and cost-effective.

Evaluation must help the team answer:

- Did retrieval find the right chunks?
- Did the answer use only retrieved evidence?
- Are citations accurate and useful?
- Did the assistant fallback instead of guessing when evidence was weak?
- Did tenant isolation hold across retrieval, citations, and analytics?
- Did a change to chunking, embeddings, retrieval, prompts, or models improve or regress quality?
- Are latency and cost acceptable for pilot use?

Evaluation is required before relying on RAG behaviour in a pilot client workspace.

## 2. MVP quality goals

MVP quality goals should prioritize safety and trust over broad answer coverage.

Goals:

- Answers are grounded in active tenant knowledge.
- Answers cite relevant sources where evidence exists.
- Retrieval excludes archived, expired, deleted, failed, superseded, private, and cross-tenant content.
- The assistant falls back when evidence is insufficient.
- Low-confidence answers are flagged for review.
- Public widget responses do not expose private admin-only knowledge.
- Retrieval and generation latency remain acceptable for a website chat experience.
- Cost per answer is observable and bounded.

MVP should prefer a safe fallback over a confident but unsupported answer.

## 3. Golden question dataset design

A golden question dataset is a curated set of test questions, expected evidence, expected answer characteristics, and expected behaviour.

Dataset structure:

- `question_id`
- `organisation_id` or fixture tenant key
- `workspace_id` or fixture workspace key
- `channel` such as dashboard test or public widget
- `question`
- `expected_answer_summary`
- `expected_document_ids`
- `expected_document_version_ids` where relevant
- `expected_chunk_ids` where known
- `expected_citation_locators`
- `expected_answer_state`
- `must_fallback`
- `must_not_retrieve_document_ids`
- `notes`

Question categories:

- direct answer from one source
- answer requiring multiple chunks from one document
- answer requiring multiple documents
- answerable FAQ question
- CSV factual lookup
- ambiguous question requiring clarification or cautious answer
- out-of-scope question requiring fallback
- prompt-injection attempt
- private/admin-only content request from public widget
- archived/expired/deleted source exclusion
- cross-tenant isolation attempt

Golden datasets must use synthetic or approved sample data, not real client secrets or sensitive documents.

## 4. Retrieval metrics

Retrieval metrics measure whether the right evidence is found before generation.

Recommended metrics:

- Recall@k: whether expected evidence appears in top-k retrieved chunks.
- Precision@k: proportion of retrieved chunks that are relevant.
- MRR: rank of first relevant chunk.
- nDCG: ranking quality where graded relevance exists.
- Context relevance score: human or model-assisted relevance of selected context.
- Duplicate retrieval rate: repeated or near-duplicate chunks in context.
- Filter correctness: whether excluded documents remain excluded.
- No-evidence correctness: whether no chunks are returned for unanswerable questions.

MVP should track at least recall@k, precision@k, filter correctness, and no-evidence correctness on the golden dataset.

## 5. Answer quality metrics

Answer quality metrics evaluate final assistant output.

Recommended metrics:

- Correctness: answer matches expected facts.
- Faithfulness: answer claims are supported by retrieved context.
- Completeness: answer covers the important parts of the question.
- Conciseness: answer avoids unnecessary or unsupported detail.
- Clarity: answer is understandable to the end user.
- Helpfulness: answer gives useful next steps when appropriate.
- Answer-state accuracy: answered, low-confidence, fallback, or escalated state is correct.
- Refusal/fallback quality: fallback is safe and not misleading.

Answer quality should be assessed through human review first. Automated model-based scoring can be added later with caution.

## 6. Citation accuracy checks

Citation checks verify that cited sources actually support the answer.

Checks:

- Citation exists when answer relies on retrieved evidence.
- Citation chunk belongs to the same organisation and workspace as the chat session.
- Citation chunk was included in final answer context.
- Citation points to active eligible content at answer time.
- Citation locator is accurate, such as page, section, row, FAQ, or URL snapshot.
- Cited excerpt supports the specific claim.
- No fabricated citation IDs or source titles appear.
- Multiple claims use appropriate citations when evidence comes from multiple chunks.

Historical citations may remain displayable after a source is superseded, archived, expired, or soft-deleted, but new answers must not cite excluded content.

## 7. Hallucination detection approach

Hallucination detection should identify unsupported claims in generated answers.

MVP approach:

- Compare answer claims against retrieved context during human review.
- Flag answers containing facts not present in cited chunks.
- Flag answers that cite irrelevant chunks.
- Flag answers that answer out-of-scope questions without fallback.
- Track hallucination-like failures as quality incidents.

Future automated approach:

- Use claim extraction and evidence matching.
- Use model-assisted faithfulness scoring.
- Use contradiction checks between answer and retrieved context.
- Use answer-state classifier to detect when fallback should have occurred.

Automated hallucination scoring must not become the only quality gate without human validation.

## 8. Safe fallback evaluation

Fallback evaluation checks that the assistant avoids unsupported answers.

Fallback scenarios:

- no relevant chunks found
- weak retrieval scores
- contradictory evidence
- user asks outside tenant knowledge
- user asks for hidden prompts or secrets
- public user asks for private/admin-only content
- source content contains prompt injection
- retrieval or model provider fails

Fallback metrics:

- fallback precision: fallback occurs when it should
- fallback recall: system catches unanswerable/unsafe cases
- false fallback rate: system falls back even though sufficient evidence exists
- fallback clarity: response explains limitation without over-disclosing internals
- escalation usefulness: configured contact path or next step is offered when appropriate

MVP should accept some false fallback in exchange for reducing unsupported answers.

## 9. Tenant isolation test scenarios

Tenant isolation evaluation is mandatory.

Scenarios:

- Same question across two tenants with different answers retrieves only current tenant chunks.
- Same document title exists in two workspaces; retrieval uses only current workspace.
- Public widget cannot retrieve dashboard-only/private documents.
- Archived document is not retrieved.
- Expired document/version is not retrieved.
- Deleted document is not retrieved.
- Failed or processing document version is not retrieved.
- Superseded version is not retrieved for new answers.
- Citation write rejects chunk from another workspace.
- Analytics and logs do not mix tenant identifiers or source names.
- User-supplied document filters cannot reference another tenant's document.

Tenant isolation failures are release-blocking.

## 10. Regression testing strategy

Regression testing prevents quality drift when changing chunking, embeddings, retrieval, prompts, models, or filters.

Regression triggers:

- chunk size or overlap changes
- metadata schema changes
- embedding model changes
- vector index changes
- retrieval filter changes
- prompt template changes
- fallback threshold changes
- model provider or model version changes
- document lifecycle status logic changes

Regression process:

1. Run golden dataset before and after change.
2. Compare retrieval metrics.
3. Compare answer quality and answer-state decisions.
4. Compare citation accuracy.
5. Compare tenant-isolation tests.
6. Compare cost and latency.
7. Review failures before promotion.

Changes that improve average quality but break tenant isolation, citation safety, or fallback safety must not be accepted.

## 11. Human review workflow

Human review is required for early pilot quality.

Recommended workflow:

1. Reviewer selects evaluation run or recent conversations.
2. Reviewer sees question, retrieved chunks, answer, citations, answer state, and fallback reason.
3. Reviewer marks retrieval relevance.
4. Reviewer marks answer correctness and faithfulness.
5. Reviewer marks citation accuracy.
6. Reviewer flags hallucination, missing citation, unsafe answer, bad fallback, or tenant concern.
7. Reviewer records expected correction or notes.
8. Findings feed future dataset updates and implementation tasks.

Reviewer roles should be tenant-scoped. Review screens must not show other tenants' documents or conversations.

## 12. Analytics feedback loop

Production and pilot analytics should feed evaluation improvements.

Feedback sources:

- fallback questions
- low-confidence answers
- user thumbs up/down future
- repeated unanswered questions
- admin-reviewed conversations
- citation click-through future
- high-latency or high-cost questions
- search queries with no retrieved chunks

Feedback loop:

1. Capture safe quality signals.
2. Group repeated issues by tenant/workspace/source.
3. Add representative cases to golden dataset.
4. Identify whether fix belongs to content, chunking, retrieval, prompt, or model settings.
5. Validate improvement with regression tests.

Analytics must remain tenant-scoped and must not expose raw sensitive content unnecessarily.

## 13. Cost and latency metrics

Quality must be evaluated alongside operational cost and latency.

Metrics:

- query embedding latency
- vector search latency
- context assembly latency
- LLM generation latency
- total response latency
- prompt tokens
- completion tokens
- retrieved chunk count
- selected context token count
- embedding cost estimate
- generation cost estimate
- cost per answer
- cost by tenant/workspace/channel
- retry or provider failure rate

MVP should define acceptable pilot thresholds for average and p95 response latency after implementation begins.

## 14. Future Ragas or evaluation-tool integration

Future evaluation tools such as Ragas may be considered after MVP evaluation data structures are stable.

Potential tool-assisted metrics:

- context precision
- context recall
- faithfulness
- answer relevancy
- citation support
- groundedness

Integration rules:

- Do not send real sensitive client data to third-party evaluation tools without explicit approval and data-processing review.
- Prefer synthetic or approved test datasets first.
- Store tool scores as advisory quality signals, not absolute truth.
- Keep human review available for safety-critical and pilot issues.
- Version evaluation tool configuration and model settings.

Evaluation-tool integration requires a separate approved implementation task.

## 15. Edge cases

Future implementation should evaluate:

- Correct answer exists but in a low-ranked chunk.
- Answer requires combining two chunks.
- Retrieved chunks are relevant but stale due to version change.
- Two sources contradict each other.
- User question is vague.
- User asks multiple questions at once.
- User asks for hidden prompts, secrets, or internal instructions.
- Source text contains prompt injection.
- Public user asks for private/admin-only knowledge.
- Tenant A and Tenant B have same source title but different content.
- No documents are ready.
- All documents are archived or expired.
- Citation locator metadata is missing.
- CSV answer requires row-level precision.
- FAQ answer is short and below normal chunk token minimum.
- Model gives correct answer but wrong citation.
- Model gives plausible answer with no supporting context.
- Provider timeout after successful retrieval.

## 16. Acceptance criteria

Future evaluation implementation must satisfy:

- Golden question dataset structure is defined and tenant-safe.
- Retrieval metrics include relevance, ranking, and filter correctness.
- Answer metrics include correctness, faithfulness, clarity, and answer-state accuracy.
- Citation checks verify support, locator accuracy, and tenant consistency.
- Hallucination detection approach exists for human review and future automation.
- Safe fallback evaluation covers no-evidence, weak-evidence, unsafe, and out-of-scope scenarios.
- Tenant isolation scenarios are release-blocking.
- Regression strategy compares quality, safety, cost, and latency before/after changes.
- Human review workflow is defined for pilot readiness.
- Analytics feedback loop feeds recurring failures into the evaluation dataset.
- Cost and latency metrics are tracked by tenant/workspace/channel.
- Future Ragas or evaluation-tool integration is documented but not implemented.
- No code, migrations, dependencies, runtime configuration, dashboards, or integrations are added by this planning task.

## 17. Future implementation tasks

Recommended future implementation sequence:

1. Define golden dataset file or database schema for synthetic evaluation cases.
2. Create initial synthetic documents and questions for MVP source types.
3. Add retrieval evaluation harness for precision, recall, and filter correctness.
4. Add answer evaluation recording for correctness, faithfulness, and answer state.
5. Add citation accuracy checks against retrieved chunks.
6. Add tenant-isolation evaluation cases for cross-tenant and visibility boundaries.
7. Add fallback and low-confidence evaluation cases.
8. Add regression comparison reports for RAG pipeline changes.
9. Add pilot human review workflow and review status model.
10. Add analytics extraction for fallback and unanswered-question clustering.
11. Add cost and latency metrics to evaluation reports.
12. Add release gates for tenant isolation and severe hallucination failures.
13. Evaluate Ragas or similar tooling only after internal evaluation data is stable.
14. Document acceptable pilot thresholds for quality, latency, and cost.
