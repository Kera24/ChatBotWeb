# Reporting Policy

Two formats. **Default to Short Report.** Only use Full Report when explicitly asked for detail, or when the change is large/architecturally significant enough that a short report would hide something the user needs to know (schema change, guardrail change, billing change, RBAC/tenant-isolation change, cross-cutting infra change).

## Short Report (default)

Four sections, no more:

1. **Files changed** — a flat list (new vs. modified is enough detail; no need to narrate each one unless something is non-obvious).
2. **Validation** — which commands were run (per `docs/validation-policy.md`) and their result (pass counts, not full output).
3. **Remaining limitations** — anything deferred, not implemented, or not verifiable in this environment. State this plainly, don't bury it.
4. **Git status** — confirm no commits/pushes were made (unless explicitly asked), and that the working tree only contains the intended changes.

Keep it scannable. This is the report for routine feature work, bug fixes, test additions, and documentation updates.

## Full Report

Used for: schema/migration changes, guardrail changes, billing changes, RBAC/tenant-isolation changes, evaluation threshold changes (should be rare and only with explicit prior instruction), cross-cutting infrastructure changes, or any task the user explicitly asked to be reported in detail.

Structure (adapt section count to what's actually relevant — don't pad):

1. What changed and why (one paragraph, not a changelog).
2. Design/architecture decisions made along the way, especially any deviation from an initial plan and why.
3. Files changed, grouped by area.
4. Validation performed, with actual commands and results.
5. Manual/live verification performed, if applicable (state explicitly if a UI feature was NOT live-verified due to environment constraints — never imply it was).
6. Remaining limitations, explicitly enumerated.
7. Environment variables or config added, if any.
8. Git status.

## Rules that apply to both formats

- Every claim ("tests pass," "build succeeds," "feature works") must be backed by a command actually run in this session — see `docs/CONSTITUTION.md`'s "Evidence-driven engineering."
- State limitations plainly. A report that hides a gap to look more complete is a worse outcome than a shorter, honest one.
- Don't repeat the user's own prompt back to them as part of the report.
- If asked "is X done," answer that question directly before anything else.
