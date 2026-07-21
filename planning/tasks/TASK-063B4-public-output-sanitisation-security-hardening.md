# TASK-063B4 - Public Output Sanitisation And Security Hardening

## Objective

Replace the provisional public message projection with a dedicated output-sanitisation and citation-validation boundary for public widget answers.

## Scope

- Dedicated `app.access.messages.output` package.
- Plain-text MVP sanitisation boundary with a documented restricted-Markdown path.
- Strict HTTPS link validation and unsafe link removal.
- HTML/script/style/object stripping using a parser-backed text extraction path.
- Deterministic leakage checks and known internal value redaction.
- System/developer-instruction leakage fallback replacement.
- Citation validation, deduplication, reindexing, marker rewriting, and public-safe projection.
- Integration into `PublicWidgetRAGAdapter` before idempotency snapshot completion.
- Tests for XSS, links, limits, leakage, citations, and endpoint snapshot safety.

## Non-Goals

- No widget SDK/UI.
- No streaming, rich embeds, file/image output, public history, tools, new providers, lead capture, analytics UI, or migrations.
- No arbitrary HTML or full Markdown rendering in the backend response.

## Acceptance Criteria

- All public message responses pass through `PublicOutputSanitiser`.
- Completed idempotency snapshots store only sanitised public output.
- Unsafe HTML, scripts, unsafe URLs, known internal values, severe prompt leakage, unsafe citations, and unsupported citation markers are removed, redacted, downgraded, or replaced safely.
- Full API and web verification pass.