"""Grader-call cache keyed by a hash of (answer, evidence, rubric version,
model) - Section 13's "caching by answer/evidence/rubric/model hash", used
to avoid re-grading identical content when reruns or repeated consistency
checks would otherwise call the model again for the same input. In-process
dict cache (an evaluation CLI run is a single short-lived process) rather
than a new database table - no migration needed for this, consistent with
Section 9's "add migration only if required".
"""

from __future__ import annotations

from hashlib import sha256

from app.evaluation.graders.context import GradingContext
from app.evaluation.graders.contracts import GraderResult
from app.evaluation.graders.rubrics import GraderDimension


def cache_key(*, dimension: GraderDimension, context: GradingContext, rubric_version: str, grader_model: str) -> str:
    payload = "␟".join([
        dimension.value, rubric_version, grader_model, context.question, context.answer, context.answer_state,
        context.evidence_block(),
    ])
    return sha256(payload.encode("utf-8")).hexdigest()


class GraderResultCache:
    def __init__(self) -> None:
        self._store: dict[str, GraderResult] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> GraderResult | None:
        result = self._store.get(key)
        if result is not None:
            self.hits += 1
        else:
            self.misses += 1
        return result

    def set(self, key: str, result: GraderResult) -> None:
        self._store[key] = result

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "entries": len(self._store)}
