# Dataset Promotion Policy

Related: [Candidate Triage Guide](./Candidate_Triage_Guide.md), [Golden Dataset Versioning Guide](./Golden_Dataset_Versioning_Guide.md).

## Rule

An `EvaluationCandidate` may only become an `EvaluationCase` through `app.repositories.evaluation_candidate_repository.promote_candidate()`, and only when `triage_status == "accepted"`. There is no automatic promotion path anywhere in this codebase — this mirrors the source spec's explicit instruction ("No automatic approval") and CLAUDE.md's evaluation-framework rule that golden-dataset changes are deliberate, not incidental.

## What promotion does

1. Builds a new `EvaluationCase` from the candidate's **redacted** `redacted_question`/`redacted_response` — never the raw production text, even though the promoting reviewer has already seen it in triage. This keeps the invariant "no raw production content in a golden dataset row" true regardless of what the reviewer had access to.
2. Copies triage-defined `expected_document_ids`/`expected_source_labels`/`expected_answerability`/root-cause-as-`category` onto the case directly; folds softer triage details (required/forbidden answer points, citation/fallback/clarification flags) into the case's `metadata_json`, the same JSON-extensibility pattern already used for isolation-category cases.
3. Increments `EvaluationDataset.version` (integer parse-and-increment; falls back to a timestamp suffix if the current version isn't a plain integer) and writes one `EvaluationDatasetVersionEvent` row recording `from_version`/`to_version`/the new case id/the candidate id/the reviewer/the changelog note.
4. Sets `candidate.promoted_case_id`/`dataset_destination_id` and writes an audit event (`evaluation_candidate.promoted`), matching the existing `add_audit_event` convention used by `review_repository.update_review_status`.

## What promotion never does

- **Never writes to `app/evaluation/fixtures/*.json`.** The checked-in golden fixture files are a separate, static, version-controlled dataset used by `eval_golden_setup.py`. Production-fed cases live only in the `evaluation_cases` DB table, distinct from that file-based set. This is what makes "never automatically export raw production prompts to version-controlled fixtures" structurally true — promotion has no code path that touches the filesystem or git.
- **Never mutates an existing `EvaluationRun` or `EvaluationResult` row.** Every run already snapshots the dataset version it ran against (`EvaluationRun.dataset_version`); a version bump after the fact does not retroactively change what an old run is understood to have tested.
- **Never bypasses triage.** There is no "promote directly from a trace" shortcut — a candidate row and an `accepted` decision are always required first.

## Provenance

`EvaluationCase.source_candidate_id` (nullable FK) is set only for production-promoted cases; hand-authored/fixture-seeded cases leave it `null`. Use it to filter "production-fed cases" (see `app.operations.eval_focused_run`'s default selection) or to trace a case back to the original candidate/signal/trace for a "why does this case exist" investigation.

## Version numbering

See the [Golden Dataset Versioning Guide](./Golden_Dataset_Versioning_Guide.md) for the full versioning model; in short, `EvaluationDataset.version` is a bare string (unchanged from the pre-existing evaluation framework), and each promotion's before/after value plus a human-readable changelog note is preserved forever in `EvaluationDatasetVersionEvent` — the dataset row itself only ever shows the current version, the event table is the history.
