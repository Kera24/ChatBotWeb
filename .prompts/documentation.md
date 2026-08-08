# Prompt Template: Documentation

Use this when the task is writing or updating documentation (not code).

## Scope

`docs/**`, `CLAUDE.md`, `.prompts/**`, `.skills/**`. See `docs/file-boundaries.md` for which existing directory a given topic belongs in.

## Constraints

- Do not create a new top-level docs directory — add to the existing structure (`docs/architecture/`, `docs/03_AI/`, `docs/04_Engineering/`, `docs/06_Operations/`, `docs/design/`, etc.).
- Verify claims against the actual current code before writing them down — documentation that's wrong is worse than no documentation, especially for files that become Claude's primary context (`CLAUDE.md`, `docs/architecture/*`).
- Cross-reference instead of duplicating — link to the existing doc that already covers something rather than re-explaining it.
- Match the terse, scannable, bullet-heavy style of the existing architecture docs — this is reference material meant to reduce future token usage, not prose meant to be read once.
- Keep `CLAUDE.md` as the index/summary layer; put depth in `docs/architecture/*.md` and link to it.

## Validation

No automated validation — the "test" is: does the doc match the actual code right now? Grep for the specific file paths/function names claimed and confirm they exist as described.

## Reporting

Short Report: files changed, what was verified against the actual code, remaining gaps.

## Expected output

Updated/new markdown files, internally consistent with the rest of `docs/`, no contradictions with `CLAUDE.md`.

## What NOT to modify

- Code files (this template is documentation-only; if the task also requires a code change, use the relevant code-area template instead).
- Existing docs' accurate content, just to make room for new content — extend, don't overwrite, unless the existing content is actually stale/wrong.
