# Prompt Variable Reference

See `docs/architecture/prompts.md` for the rendering bridge this feeds. This document lists every variable a prompt layer's content can reference, and the validation rules around them.

## Validation model

`app.prompts.render.PromptVariableSpec(name, required, max_length)` — a list of these is stored as `PromptVersion.variables_schema_json`. Two checks apply, both raising `app.ai.errors.PromptValidationError`:

- **Allow-list**: `validate_template_variables()` parses the content with `string.Formatter().parse()` and rejects any `{placeholder}` not in the declared schema — the same technique `app.ai.prompt_registry.PromptRegistry` already applies to the code-defined default template.
- **Required-at-render**: `render_layer_content()`/`validate_variable_values()` raises if a required variable has no value at render time, and enforces `max_length` per variable when set.

A per-layer content size ceiling (`DEFAULT_MAX_LAYER_CONTENT_CHARS`, 6,000 characters) applies at draft-creation time; a combined rendered-prompt ceiling (`DEFAULT_MAX_RENDERED_PROMPT_CHARS`, 24,000 characters) applies to the final assembled system+user prompt at render time.

## `platform_core` variables

Declared in `app.prompts.defaults.PLATFORM_CORE_VARIABLES`:

| Variable | Required | Max length | Source |
|---|---|---|---|
| `question` | Yes | — | The user's message, passed by `RAGOrchestrator.answer()`. |
| `context` | Yes | — | The assembled, sanitised retrieved-evidence block (Layer E output). |
| `assistant_persona` | No | 2,000 | The rendered content of the workspace's active `assistant_persona_tone` version, or `""` if none is deployed. |
| `organisation_guidance` | No | 2,000 | The rendered content of the workspace's active `organisation_guidance` version, or `""` if none is deployed. |

`{question}`/`{context}` are only ever populated by the orchestrator, never by a template author — they are documented here because they are legal placeholders in `platform_core` content, not because a version's author supplies their values.

## `assistant_persona_tone` / `organisation_guidance` variables

These two layers are **plain authored text with no further runtime templating in the MVP** — `app.prompts.defaults.EMPTY_LAYER_VARIABLES` is the default (empty) schema, and `resolve_composite_prompt()` inserts each layer's raw `content` directly into `platform_core`'s `{assistant_persona}`/`{organisation_guidance}` slots without calling `.format()` on it again. An author *may* declare named variables via the version-create API (`variables_schema` field) if they want a placeholder they fill in once at draft time (e.g. `{assistant_name}`, `{fallback_contact}`) — but since there is no per-request value source for author-defined variables on these two layers, any such variable must be resolved to a literal value before the version leaves `draft` status; it is not filled in per-request the way `question`/`context` are.

## Sensitive values

No prompt-management variable is ever a secret or credential — `apps/api/app/core/config.py`'s secret-shaped settings are never exposed through this system. Rendered prompt content (system + user) is subject to the same redaction/retention path as any other AI trace content when persisted (`AIModelCallTrace.raw_prompt_preview`, via `app.observability.redaction.apply_retention_policy`) — this feature does not introduce a new storage path for prompt content outside that existing control.
