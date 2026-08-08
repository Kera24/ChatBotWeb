# Golden Dataset Versioning Guide

Related: [Dataset Promotion Policy](./Dataset_Promotion_Policy.md), [Regression Release Policy](../06_Operations/Regression_Release_Policy.md).

## Model

`EvaluationDataset.version` (a plain string, e.g. `"1"`, `"2"`) was already part of the pre-existing evaluation framework (`docs/architecture/evaluation.md`) — every `EvaluationRun` snapshots the version it ran against in `EvaluationRun.dataset_version`. The feedback loop adds one thing on top: `EvaluationDatasetVersionEvent`, an append-only changelog of *why* the version moved.

```
EvaluationDataset (mutable "current version")
   ↓ one row per bump
EvaluationDatasetVersionEvent (immutable history: from_version, to_version, case_id, candidate_id, reviewer, changelog_note, created_at)
```

Every version bump today comes from exactly one promoted candidate (one event row per promotion, one case per event). Hand-authored cases added the old way (`POST /evaluation/datasets/{id}/cases`) do not bump the version or create an event row — that endpoint is unchanged. If a future need arises to version-bump for a batch of hand-authored cases, extend `evaluation_repository.create_case`'s caller to also call the version-bump logic, rather than inventing a second versioning mechanism.

## Reading the history

`GET /workspaces/{id}/evaluation-dataset-versions` (dashboard: `/feedback-loop/versions`) lists events newest-first, optionally filtered by `dataset_id`. Each entry shows the version transition, the changelog note, and a link to the promoting candidate (when one exists).

## Numbering scheme

`_increment_dataset_version()` in `evaluation_candidate_repository.py`: if the current version parses as an integer, increment it (`"3"` → `"4"`); otherwise append a Unix-timestamp suffix (`"2026.1"` → `"2026.1.1770000000"`) rather than failing. This keeps promotion working even against a dataset whose version string doesn't follow the plain-integer convention, without silently overwriting or guessing at a more "correct" scheme.

## Why events, not a mutable log

`EvaluationRun.dataset_version` already answers "what version did this run test" for any historical run — that's why version events don't need to (and don't) touch existing runs. The event table exists purely to answer "why is the dataset at version N" and "who approved case X" for a human audit trail, which the bare version string on its own can't provide once more than one promotion has happened.
