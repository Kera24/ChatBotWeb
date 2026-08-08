# Production Failure Intake Runbook

Related: [Candidate Triage Guide](../04_Engineering/Candidate_Triage_Guide.md), [Privacy and Redaction Policy](../03_AI/Continuous_Evaluation_Privacy_and_Redaction_Policy.md).

Audience: whoever is on point for turning a real production incident (a customer complaint, a support ticket, an on-call finding) into a tracked evaluation candidate.

## If you have a specific bad answer to report

1. Find the source: the AI trace (`/observability/traces/<id>`), the conversation (`/conversations/<id>`), or the review-queue item (`/review/unanswered/<id>`) that corresponds to the bad answer. Any of the three works — they carry the same underlying `ChatMessage`/`AITrace` data.
2. Click **Create evaluation candidate** on that page. This pre-links the candidate to the source (`source_trace_id`/`source_conversation_id`/`source_message_id`) so a reviewer can pull up the original context later through a controlled, authorised link — never by copying raw content into the candidate itself.
3. Pick the closest `signal_type` (`support_report` for an external report, `manual_selection` for something you found by inspection) and severity, and describe what happened in the question/response fields — these are redacted server-side before storage, so it's safe to paste the customer's actual wording here; don't paste anything beyond what's needed to reproduce the issue (no account numbers, no unrelated PII even if present in the source).
4. Submit. The candidate lands in `/feedback-loop` with `triage_status = "new"`, ready for a reviewer.

## If you don't have a specific trace (a vague complaint, a pattern you've noticed)

Use the same "Create evaluation candidate" flow from any related trace/conversation you can find, or navigate directly to `/feedback-loop/candidates/new?assistant=<id>` and fill in the question/response from memory/notes as best you can, noting in the notes field that this is reconstructed rather than sourced from a specific trace.

## If it's a systemic pattern, not one bad answer

Don't create ten near-identical candidates by hand — the nightly `production_signal_scan` (see [Nightly Evaluation VPS Guide](./Nightly_Evaluation_VPS_Guide.md)) already deduplicates repeat occurrences of the same underlying question into one candidate with a rising `occurrence_count`. If you're seeing a pattern across *different* questions (e.g. "everything about refunds is fallback-ing"), create one representative candidate per distinct question and note the pattern in each one's notes field — the root-cause category and reviewer notes are how this gets tied together during triage, not a new grouping mechanism.

## What happens next

A reviewer picks it up from `/feedback-loop` — see the [Candidate Triage Guide](../04_Engineering/Candidate_Triage_Guide.md) for the full workflow (classify → accept/reject/duplicate → promote). You are not expected to triage your own report; intake and triage are deliberately separate steps so a second person confirms it's a real, well-scoped defect before it enters the golden dataset.

## Privacy

Everything written into a candidate — question, response, notes — is redacted server-side (`app.observability.redaction.redact_free_text`) before it's stored, and evidence references are structural only (document/chunk ids and titles, never quoted content). See the [Privacy and Redaction Policy](../03_AI/Continuous_Evaluation_Privacy_and_Redaction_Policy.md) for exactly what is and isn't captured. Still: don't paste more than the minimum needed to reproduce the issue — redaction catches known patterns (emails, phone numbers, API keys, tokens), not everything a human might recognize as sensitive.
