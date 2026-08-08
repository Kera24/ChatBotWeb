"""Resolves the effective composite system/user prompt for one request,
engaging the DB-backed layered prompt system only when something has actually
been deployed through it - a workspace/widget with zero prompt-management
activity gets `None` back and the caller (app.ai.rag_orchestrator) falls
through to the unchanged code-defined default, byte for byte.

Caller contract (see docs/architecture/prompts.md's fail-open/fail-loud
design decision): this module never swallows exceptions itself - the caller
decides. app.ai.rag_orchestrator wraps this call in try/except and falls back
to `None` (recording a "degraded" stage, not silently) for organic production/
dashboard/widget traffic, but lets the exception propagate when
`prompt_version_override_id` was set (an evaluation/promotion-gate context,
where correctness matters more than availability).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.prompt_registry import RenderedPrompt
from app.db.models.prompt import (
    LAYER_ASSISTANT_PERSONA_TONE,
    LAYER_ORGANISATION_GUIDANCE,
    LAYER_PLATFORM_CORE,
    PromptDeployment,
    PromptExperiment,
    PromptTemplate,
    PromptVersion,
)
from app.prompts import defaults as prompt_defaults
from app.prompts.experiment_assignment import ARM_CANDIDATE, assign_arm, is_experiment_live
from app.prompts.render import (
    assert_max_rendered_length,
    composite_checksum,
    composite_version_label,
    render_layer_content,
    variables_schema_from_json,
)

_CACHE_TTL_SECONDS = 30
# Cache holds only {layer: active_version_id} maps (plain strings), never ORM
# rows, since rows are bound to the session that loaded them - see
# app.observability's own precedent of never caching session-bound objects
# across requests.
_deployment_cache: dict[str, tuple[float, dict[str, str]]] = {}

_PLATFORM_CACHE_KEY = "__platform__"


class PromptResolutionError(Exception):
    """Raised only when the caller explicitly requested one specific
    prompt_version_override_id and resolution could not honour it exactly."""


@dataclass(frozen=True)
class ResolvedComposite:
    rendered: RenderedPrompt
    resolved_layer_version_ids: dict[str, str]
    experiment_id: str | None = None
    experiment_arm: str | None = None


def invalidate_cache(widget_id: str | None = None) -> None:
    """Called by app.repositories.prompt_repository after any deploy/rollback/
    experiment-status change so the hot-path cache never serves a stale
    active-version mapping for longer than one write."""
    if widget_id is None:
        _deployment_cache.clear()
    else:
        _deployment_cache.pop(widget_id, None)
        _deployment_cache.pop(_PLATFORM_CACHE_KEY, None)


def resolve_composite_prompt(
    db: Session,
    *,
    prompt_key: str,
    organisation_id: str,
    workspace_id: str,
    widget_id: str | None,
    question: str,
    context: str,
    conversation_id: str | None,
    prompt_version_override_id: str | None = None,
) -> ResolvedComposite | None:
    """May raise PromptResolutionError or any underlying DB/validation error -
    the caller decides whether to catch (organic traffic) or propagate
    (explicit override requested). See module docstring."""
    active_by_layer = _fetch_active_version_ids(db, widget_id=widget_id)

    override_version: PromptVersion | None = None
    override_layer: str | None = None
    if prompt_version_override_id is not None:
        override_version = db.get(PromptVersion, prompt_version_override_id)
        if override_version is None:
            raise PromptResolutionError(f"Prompt version override not found: {prompt_version_override_id}")
        template = db.get(PromptTemplate, override_version.template_id)
        if template is None:
            raise PromptResolutionError(f"Prompt template not found for override version: {prompt_version_override_id}")
        override_layer = template.layer
        active_by_layer = {**active_by_layer, override_layer: override_version.id}

    if not active_by_layer:
        return None  # fully dormant scope - organic fallback to the code default

    experiment: PromptExperiment | None = None
    experiment_arm: str | None = None
    if prompt_version_override_id is None and widget_id is not None:
        experiment = _find_live_experiment(db, widget_id=widget_id)
        if experiment is not None:
            unit_key = conversation_id or widget_id
            experiment_arm = assign_arm(experiment, unit_key)
            chosen_version_id = experiment.candidate_version_id if experiment_arm == ARM_CANDIDATE else experiment.control_version_id
            active_by_layer = {**active_by_layer, experiment.layer: chosen_version_id}

    version_ids = {version_id for version_id in active_by_layer.values() if version_id}
    versions_by_id = _fetch_versions(db, version_ids)

    layer_content: dict[str, str] = {}
    layer_version_numbers: dict[str, int] = {}
    layer_checksums: list[str] = []
    resolved_layer_version_ids: dict[str, str] = {}

    for layer in (LAYER_PLATFORM_CORE, LAYER_ASSISTANT_PERSONA_TONE, LAYER_ORGANISATION_GUIDANCE):
        version_id = active_by_layer.get(layer)
        version = versions_by_id.get(version_id) if version_id else None
        if version is not None:
            layer_content[layer] = version.content
            layer_version_numbers[layer] = version.version_number
            layer_checksums.append(version.checksum)
            resolved_layer_version_ids[layer] = version.id
        else:
            layer_content[layer] = prompt_defaults.DEFAULT_LAYER_CONTENT[layer]

    system_template, _, user_template = layer_content[LAYER_PLATFORM_CORE].partition(prompt_defaults.PLATFORM_CORE_SEPARATOR)
    if not user_template:
        # Platform core content didn't carry a user-template half (shouldn't
        # happen for anything created through the repository layer, which
        # always writes both halves) - fall back to the default user template
        # rather than sending a malformed request to the provider.
        user_template = prompt_defaults.PLATFORM_CORE_USER_TEMPLATE

    variables = {
        "question": question,
        "context": context,
        "assistant_persona": layer_content[LAYER_ASSISTANT_PERSONA_TONE],
        "organisation_guidance": layer_content[LAYER_ORGANISATION_GUIDANCE],
    }
    platform_core_version = versions_by_id.get(active_by_layer.get(LAYER_PLATFORM_CORE))
    variables_schema = (
        variables_schema_from_json(platform_core_version.variables_schema_json)
        if platform_core_version is not None
        else prompt_defaults.PLATFORM_CORE_VARIABLES
    )
    system_prompt = render_layer_content(system_template, variables, variables_schema)
    user_prompt = render_layer_content(user_template, variables, variables_schema)
    assert_max_rendered_length(system_prompt + user_prompt)

    version_label = composite_version_label(layer_version_numbers) if layer_version_numbers else "default"
    prompt_hash = composite_checksum(layer_checksums) if layer_checksums else "default"

    rendered = RenderedPrompt(
        prompt_key=prompt_key,
        version=version_label,
        prompt_hash=prompt_hash,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    if prompt_version_override_id is not None and override_layer is not None:
        actual_override_resolution = resolved_layer_version_ids.get(override_layer)
        if actual_override_resolution != prompt_version_override_id:
            raise PromptResolutionError(
                f"Resolved composite did not use the requested override version {prompt_version_override_id} for layer {override_layer}."
            )

    return ResolvedComposite(
        rendered=rendered,
        resolved_layer_version_ids=resolved_layer_version_ids,
        experiment_id=experiment.id if experiment is not None else None,
        experiment_arm=experiment_arm,
    )


def _fetch_active_version_ids(db: Session, *, widget_id: str | None) -> dict[str, str]:
    cache_key = widget_id or _PLATFORM_CACHE_KEY
    cached = _deployment_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return dict(cached[1])

    result: dict[str, str] = {}
    platform_deployment = db.execute(
        select(PromptDeployment).where(
            PromptDeployment.layer == LAYER_PLATFORM_CORE,
            PromptDeployment.organisation_id.is_(None),
            PromptDeployment.workspace_id.is_(None),
            PromptDeployment.widget_id.is_(None),
        )
    ).scalar_one_or_none()
    if platform_deployment is not None:
        result[LAYER_PLATFORM_CORE] = platform_deployment.active_version_id

    if widget_id is not None:
        widget_deployments = db.execute(
            select(PromptDeployment).where(
                PromptDeployment.widget_id == widget_id,
                PromptDeployment.layer.in_([LAYER_ASSISTANT_PERSONA_TONE, LAYER_ORGANISATION_GUIDANCE]),
            )
        ).scalars().all()
        for deployment in widget_deployments:
            result[deployment.layer] = deployment.active_version_id

    _deployment_cache[cache_key] = (now, dict(result))
    return result


def _fetch_versions(db: Session, version_ids: set[str]) -> dict[str, PromptVersion]:
    if not version_ids:
        return {}
    rows = db.execute(select(PromptVersion).where(PromptVersion.id.in_(version_ids))).scalars().all()
    return {row.id: row for row in rows}


def _find_live_experiment(db: Session, *, widget_id: str) -> PromptExperiment | None:
    experiments = db.execute(
        select(PromptExperiment).where(PromptExperiment.widget_id == widget_id, PromptExperiment.status == "running")
    ).scalars().all()
    for experiment in experiments:
        if is_experiment_live(experiment):
            return experiment
    return None
