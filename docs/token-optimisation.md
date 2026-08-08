# Token Optimisation Guide

Why this whole framework (`CLAUDE.md`, `docs/architecture/*`, `.skills/*`, `.prompts/*`) exists: to make future prompts short and future sessions fast, by moving repeated context out of the prompt and into files Claude reads once per task instead of the user re-explaining every time.

## How future prompts should be written

Short-form is now sufficient for routine work:

```
Use the Frontend UI skill. Implement Task X: <one-sentence description>.
```

```
Use the Observability skill. Add a new alert threshold for embedding error rate.
```

Only add extra detail in the prompt when the task is genuinely novel (not covered by an existing skill/architecture doc) or when a decision needs to be made that the framework can't make on its own (e.g. "should this be `org_owner`-only or viewer-inclusive" for a judgment call outside existing precedent).

## How Claude should avoid rediscovering architecture

1. Read `CLAUDE.md` first (short, indexes everything else).
2. Read the named skill's `SKILL.md` if one was named.
3. Read the relevant `docs/architecture/*.md` file(s) for the subsystem.
4. Check `docs/file-boundaries.md` for the specific feature.
5. Only then start exploring the actual code — and even then, prefer targeted reads (the specific file the doc points to) over broad exploration.

If a task doesn't name a skill, infer the closest one from `docs/file-boundaries.md`'s feature list before falling back to open-ended exploration.

## How to minimise unnecessary repository exploration

- Trust the architecture docs' file paths and function names as a starting point — verify with a targeted `Read`/`Grep` on the specific claim, not a broad `Explore` agent, unless the docs are silent on the area.
- Do not re-derive things already stated in `docs/architecture/*` (e.g. "how does RBAC work" — it's answered in `authentication.md` and `backend.md`; don't re-trace `deps.py` from scratch).
- Use `Grep`/`Glob` for a single known symbol; reserve the `Explore` agent for genuinely open-ended "where does X live" questions not covered by `docs/file-boundaries.md`.

## How to reuse documentation

- Point users/yourself at the existing doc instead of re-explaining inline. If asked "how does billing work," the answer is "see `docs/architecture/billing.md`" plus a one-line summary, not a full re-derivation.
- When a task changes something a doc describes, update that doc in the same turn — this is what keeps future token costs low; a stale doc costs more tokens later (in re-discovery + confusion) than the update costs now.

## How to avoid repetitive analysis

- Don't re-run "audit the whole telemetry/observability surface" style broad research if `docs/03_AI/AI_Observability_Architecture.md` (or the relevant architecture doc) already answers the question — read it first, only research the specific gap it doesn't cover.
- Don't re-derive "what's the test fixture convention" — `docs/architecture/testing.md` states it.
- Don't re-derive "what's the RBAC pattern" — `docs/architecture/backend.md` and `authentication.md` state it.

## How to use existing skills

Each `.skills/<name>/SKILL.md` states its own scope, files typically/never modified, validation commands, and common pitfalls. Load it, follow it, don't re-derive the same information by exploring the codebase from scratch. If a skill is missing something needed for the current task, extend the skill file itself (so the gap doesn't recur) rather than only solving it inline.

## How to minimise token usage generally

- Default to Short Report (`docs/reporting-policy.md`) — Full Report only when warranted.
- Default to the narrowest validation command set (`docs/validation-policy.md`) — not `npm run verify` for every change.
- Prefer editing files directly over reading large swaths of unrelated code "just in case."
- When spawning a subagent for research, give it a tightly scoped question referencing the specific docs/skills already known to be relevant, rather than an open-ended "explore the codebase" prompt.
- Keep documentation updates in this framework terse and scannable (bullet points, tables, file paths) — this framework's own writing style is itself a token-optimisation choice; match it when extending these docs.

## Signal that the framework needs updating

If you find yourself re-deriving something from source code that really should have been in `docs/architecture/*` or a skill file, that's a signal to add it there before finishing the task — not just solve the immediate problem and move on. This is how the framework stays worth maintaining.
