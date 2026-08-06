"""Local Ollama-backed grader (Section 2's "local Ollama grader where
available"). Mirrors app.services.embeddings.OllamaEmbeddingProvider's HTTP
call pattern (httpx, try/except httpx.HTTPError, status-code check, JSON
shape validation) but calls Ollama's /api/generate completion endpoint
instead of /api/embed, requesting structured JSON output via `format:
"json"` (a native Ollama feature - the model is instructed to only emit
valid JSON), then validates the JSON against the GraderResult/PairwiseVerdict
pydantic contracts (contracts.py) rather than trusting free-form parsing as
the only safety net (Section 3's explicit requirement).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from app.evaluation.graders.context import GradingContext
from app.evaluation.graders.contracts import GraderResult, PairwiseVerdict
from app.evaluation.graders.errors import GraderOutputValidationError, GraderProviderError, GraderTimeoutError
from app.evaluation.graders.prompts import GRADER_PROMPT_VERSION, build_dimension_prompt, build_pairwise_prompt
from app.evaluation.graders.provider import GraderProvider
from app.evaluation.graders.rubrics import RUBRIC_VERSION, RubricDefinition


def check_ollama_grader_model_available(*, base_url: str, model_name: str, timeout_seconds: float = 5.0) -> None:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
    except httpx.HTTPError as exc:
        raise GraderProviderError(
            f"Could not reach Ollama at {base_url!r} to verify grader model {model_name!r} is installed: {exc}. "
            "Is the Ollama runtime running (`ollama serve`)?"
        ) from exc
    if response.status_code != 200:
        raise GraderProviderError(f"Ollama returned HTTP {response.status_code} listing models: {response.text[:500]}")
    models = response.json().get("models", [])
    bare_name = model_name.split(":")[0]
    if not any(m.get("model") == model_name or m.get("name") == model_name or m.get("model", "").split(":")[0] == bare_name for m in models):
        raise GraderProviderError(f"Ollama does not have model {model_name!r} installed. Install it with `ollama pull {model_name}`.")


@dataclass
class OllamaGraderProvider(GraderProvider):
    model_name: str
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0  # deterministic-where-supported, per Section 6's "deterministic temperature where supported"
    max_tokens: int = 512
    timeout_seconds: float = 60.0
    provider_key: str = "ollama"
    display_name: str = "Local Ollama Grader"

    def grade(self, *, rubric: RubricDefinition, context: GradingContext) -> GraderResult:
        system_prompt, user_prompt = build_dimension_prompt(rubric=rubric, context=context)
        raw = self._call(system_prompt=system_prompt, user_prompt=user_prompt)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GraderOutputValidationError(f"Grader model {self.model_name!r} did not return valid JSON: {raw[:300]!r}") from exc
        payload.setdefault("passed", payload.get("score", 0.0) >= rubric.pass_threshold)
        payload["dimension"] = rubric.dimension.value
        payload["rubric_version"] = RUBRIC_VERSION
        payload["prompt_version"] = GRADER_PROMPT_VERSION
        payload["grader_provider"] = self.provider_key
        payload["grader_model"] = self.model_name
        try:
            return GraderResult.model_validate(payload)
        except ValidationError as exc:
            raise GraderOutputValidationError(f"Grader model {self.model_name!r} returned JSON that did not match the GraderResult contract: {exc}") from exc

    def compare_pairwise(self, *, rubric: RubricDefinition, question: str, answer_a: str, answer_b: str, evidence_block: str, order_swapped: bool = False) -> PairwiseVerdict:
        system_prompt, user_prompt = build_pairwise_prompt(rubric=rubric, question=question, answer_a=answer_a, answer_b=answer_b, evidence_block=evidence_block)
        raw = self._call(system_prompt=system_prompt, user_prompt=user_prompt)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GraderOutputValidationError(f"Grader model {self.model_name!r} did not return valid JSON: {raw[:300]!r}") from exc
        payload["rubric_dimension"] = rubric.dimension.value
        payload["order_swapped"] = order_swapped
        payload["grader_provider"] = self.provider_key
        payload["grader_model"] = self.model_name
        payload["prompt_version"] = GRADER_PROMPT_VERSION
        try:
            return PairwiseVerdict.model_validate(payload)
        except ValidationError as exc:
            raise GraderOutputValidationError(f"Grader model {self.model_name!r} returned JSON that did not match the PairwiseVerdict contract: {exc}") from exc

    def _call(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/api/generate",
                json={
                    "model": self.model_name,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise GraderTimeoutError(f"Grader call to Ollama model {self.model_name!r} exceeded {self.timeout_seconds}s.") from exc
        except httpx.HTTPError as exc:
            raise GraderProviderError(f"Could not reach Ollama at {self.base_url!r} for grading: {exc}. Is the Ollama runtime running (`ollama serve`)?") from exc
        if response.status_code != 200:
            raise GraderProviderError(f"Ollama returned HTTP {response.status_code} for grader model {self.model_name!r}: {response.text[:500]}")
        payload = response.json()
        text = payload.get("response")
        if not text:
            raise GraderOutputValidationError(f"Ollama returned no response text for grader model {self.model_name!r}. Payload: {payload!r}")
        return text
