"""Shared safe-templating primitives for the versioned prompt-management
system (app.prompts.*, app.evaluation.prompt_promotion_gate,
app.repositories.prompt_repository).

Uses the same Formatter-based allowed-variable-only validation technique
already established in app.ai.prompt_registry.PromptRegistry - reimplemented
here (not imported) because app.ai.prompt_registry is lower-level than this
package and must not depend on it; the two validators must stay behaviourally
equivalent, not literally shared code.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from string import Formatter

from app.ai.errors import PromptValidationError

# Hard ceiling on any single rendered prompt (system + user combined). Chosen
# generously above the current single-template prompt's size so it only ever
# fires on a genuine authoring mistake (e.g. runaway organisation guidance
# text), not on normal content.
DEFAULT_MAX_RENDERED_PROMPT_CHARS = 24_000

# Per-layer content ceiling, enforced at draft-creation time so a single
# customer-editable layer (persona/tone, organisation guidance) can't by
# itself blow the composite budget.
DEFAULT_MAX_LAYER_CONTENT_CHARS = 6_000


@dataclass(frozen=True)
class PromptVariableSpec:
    name: str
    required: bool = True
    max_length: int | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "required": self.required, "max_length": self.max_length}


def variables_schema_from_json(raw: list[dict] | None) -> list[PromptVariableSpec]:
    if not raw:
        return []
    return [PromptVariableSpec(name=item["name"], required=item.get("required", True), max_length=item.get("max_length")) for item in raw]


def variables_schema_to_json(schema: list[PromptVariableSpec]) -> list[dict]:
    return [spec.as_dict() for spec in schema]


def validate_template_variables(content: str, allowed_variable_names: set[str]) -> None:
    """Raises PromptValidationError if `content` references any {variable}
    placeholder that isn't in `allowed_variable_names` - the same allow-list
    discipline app.ai.prompt_registry already applies to the code-defined
    template, extended to DB-authored layer content."""
    formatter = Formatter()
    for _literal, field_name, _format_spec, _conversion in formatter.parse(content):
        if field_name is not None and field_name not in allowed_variable_names:
            raise PromptValidationError(f"Template references unknown variable: {field_name}")


def validate_variable_values(variables_schema: list[PromptVariableSpec], values: dict[str, str]) -> None:
    for spec in variables_schema:
        if spec.required and spec.name not in values:
            raise PromptValidationError(f"Missing required prompt variable: {spec.name}")
        value = values.get(spec.name)
        if value is not None and spec.max_length is not None and len(value) > spec.max_length:
            raise PromptValidationError(f"Prompt variable '{spec.name}' exceeds max length {spec.max_length}.")


def validate_layer_content(content: str, variables_schema: list[PromptVariableSpec], *, max_chars: int = DEFAULT_MAX_LAYER_CONTENT_CHARS) -> None:
    """Authoring-time validation for one layer's draft content: allowed
    variables only, and a per-layer size ceiling. Does not inspect content for
    injection-style phrases - that class of check is a UX aid at best (see
    docs/architecture/prompts.md's security-policy section for why it isn't
    treated as a safety boundary here) and is intentionally not implemented
    as a blocking rule to avoid a false sense of security."""
    if len(content) > max_chars:
        raise PromptValidationError(f"Prompt layer content exceeds maximum length of {max_chars} characters.")
    allowed = {spec.name for spec in variables_schema}
    validate_template_variables(content, allowed)


def render_layer_content(content: str, variables: dict[str, str], variables_schema: list[PromptVariableSpec]) -> str:
    validate_variable_values(variables_schema, variables)
    safe_variables = {key: str(value) for key, value in variables.items()}
    try:
        return content.format(**safe_variables)
    except KeyError as exc:
        raise PromptValidationError(f"Missing prompt variable at render time: {exc}") from exc


def layer_checksum(*, layer: str, version_number: int, content: str, variables_schema: list[PromptVariableSpec]) -> str:
    payload = "\n".join(
        [
            layer,
            str(version_number),
            content,
            ",".join(f"{spec.name}:{spec.required}:{spec.max_length}" for spec in variables_schema),
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def composite_version_label(layer_versions: dict[str, int]) -> str:
    """A short, stable, human-readable composite version label (e.g.
    "core:v3+persona:v2+guidance:v1") stamped into the legacy scalar
    prompt_version field for backward-compatible display/filtering. The
    structured, authoritative record is the resolved_layer_version_ids map
    stored alongside it (see app.prompts.resolution)."""
    short_names = {"platform_core": "core", "assistant_persona_tone": "persona", "organisation_guidance": "guidance"}
    parts = [f"{short_names.get(layer, layer)}:v{version}" for layer, version in layer_versions.items()]
    return "+".join(parts)


def composite_checksum(ordered_layer_checksums: list[str]) -> str:
    return sha256("\n".join(ordered_layer_checksums).encode("utf-8")).hexdigest()


def assert_max_rendered_length(text: str, *, max_chars: int = DEFAULT_MAX_RENDERED_PROMPT_CHARS) -> None:
    if len(text) > max_chars:
        raise PromptValidationError(f"Rendered prompt exceeds maximum length of {max_chars} characters.")
