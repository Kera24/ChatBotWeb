from hashlib import sha256
from string import Formatter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.errors import PromptNotFoundError, PromptValidationError


class PromptDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_key: str
    display_name: str
    description: str
    category: str


class PromptVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_key: str
    version: str
    system_template: str
    user_template: str
    required_variables: tuple[str, ...]
    optional_variables: tuple[str, ...] = ()
    status: str = "draft"
    prompt_hash: str


class RenderedPrompt(BaseModel):
    prompt_key: str
    version: str
    prompt_hash: str
    system_prompt: str
    user_prompt: str


class PromptRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, PromptDefinition] = {}
        self._versions: dict[tuple[str, str], PromptVersion] = {}

    def register_definition(self, definition: PromptDefinition) -> None:
        if definition.prompt_key in self._definitions:
            raise ValueError(f"Prompt definition already registered: {definition.prompt_key}")
        self._definitions[definition.prompt_key] = definition

    def register_version(self, version: PromptVersion) -> None:
        if version.prompt_key not in self._definitions:
            raise PromptNotFoundError(f"Prompt definition not found: {version.prompt_key}")
        key = (version.prompt_key, version.version)
        if key in self._versions:
            raise ValueError(f"Prompt version already registered: {version.prompt_key}@{version.version}")
        expected_hash = stable_prompt_hash(
            prompt_key=version.prompt_key,
            version=version.version,
            system_template=version.system_template,
            user_template=version.user_template,
            required_variables=version.required_variables,
            optional_variables=version.optional_variables,
        )
        if version.prompt_hash != expected_hash:
            raise PromptValidationError("Prompt hash does not match prompt content.")
        self._validate_template_variables(version)
        self._versions[key] = version

    def get_definition(self, prompt_key: str) -> PromptDefinition:
        definition = self._definitions.get(prompt_key)
        if definition is None:
            raise PromptNotFoundError(f"Prompt definition not found: {prompt_key}")
        return definition

    def get_version(self, prompt_key: str, version: str) -> PromptVersion:
        prompt_version = self._versions.get((prompt_key, version))
        if prompt_version is None:
            raise PromptNotFoundError(f"Prompt version not found: {prompt_key}@{version}")
        return prompt_version

    def resolve_active(self, prompt_key: str) -> PromptVersion:
        self.get_definition(prompt_key)
        active_versions = [
            version for key, version in self._versions.items()
            if key[0] == prompt_key and version.status == "active"
        ]
        if not active_versions:
            raise PromptNotFoundError(f"Active prompt version not found: {prompt_key}")
        return sorted(active_versions, key=lambda item: item.version)[-1]

    def render(self, prompt_key: str, variables: dict[str, Any], *, version: str | None = None) -> RenderedPrompt:
        prompt_version = self.get_version(prompt_key, version) if version else self.resolve_active(prompt_key)
        self.validate_variables(prompt_version, variables)
        safe_variables = {key: str(value) for key, value in variables.items()}
        return RenderedPrompt(
            prompt_key=prompt_version.prompt_key,
            version=prompt_version.version,
            prompt_hash=prompt_version.prompt_hash,
            system_prompt=prompt_version.system_template.format(**safe_variables),
            user_prompt=prompt_version.user_template.format(**safe_variables),
        )

    def validate_variables(self, prompt_version: PromptVersion, variables: dict[str, Any]) -> None:
        missing = [key for key in prompt_version.required_variables if key not in variables]
        if missing:
            raise PromptValidationError(f"Missing required prompt variables: {', '.join(missing)}")

    def list_definitions(self) -> list[PromptDefinition]:
        return list(self._definitions.values())

    def list_versions(self, prompt_key: str | None = None) -> list[PromptVersion]:
        versions = list(self._versions.values())
        if prompt_key is None:
            return versions
        return [version for version in versions if version.prompt_key == prompt_key]

    @staticmethod
    def _validate_template_variables(version: PromptVersion) -> None:
        allowed = set(version.required_variables) | set(version.optional_variables)
        formatter = Formatter()
        for template in (version.system_template, version.user_template):
            for _literal, field_name, _format_spec, _conversion in formatter.parse(template):
                if field_name is not None and field_name not in allowed:
                    raise PromptValidationError(f"Template references unknown variable: {field_name}")


def stable_prompt_hash(
    *,
    prompt_key: str,
    version: str,
    system_template: str,
    user_template: str,
    required_variables: tuple[str, ...],
    optional_variables: tuple[str, ...] = (),
) -> str:
    payload = "\n".join(
        [
            prompt_key,
            version,
            system_template,
            user_template,
            ",".join(required_variables),
            ",".join(optional_variables),
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def register_default_grounded_rag_prompt(registry: PromptRegistry) -> None:
    prompt_key = "grounded_rag_answer"
    registry.register_definition(
        PromptDefinition(
            prompt_key=prompt_key,
            display_name="Grounded RAG Answer",
            description="Answer from retrieved context with citations and safe fallback.",
            category="rag",
        )
    )
    system_template = (
        "You are a source-grounded assistant. Answer only from supplied context. "
        "Cite factual claims with numbered citations. If context is insufficient, say the knowledge base does not contain enough information. Do not guess."
    )
    user_template = "Question:\n{question}\n\nContext:\n{context}\n\nAnswer with citations."
    required = ("question", "context")
    prompt_hash = stable_prompt_hash(
        prompt_key=prompt_key,
        version="v1",
        system_template=system_template,
        user_template=user_template,
        required_variables=required,
    )
    registry.register_version(
        PromptVersion(
            prompt_key=prompt_key,
            version="v1",
            system_template=system_template,
            user_template=user_template,
            required_variables=required,
            status="active",
            prompt_hash=prompt_hash,
        )
    )
