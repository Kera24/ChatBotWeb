"""Structured grader output contracts. Every grader call - mock or real -
must produce one of these, never a free-form string as the only contract
(Section 3's explicit requirement). Pydantic gives strict validation:
malformed provider output raises ValidationError, which callers convert to
GraderOutputValidationError (errors.py) and handle safely (engine.py records
a clearly-labelled 'malformed output' result rather than crashing the run).
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.evaluation.graders.rubrics import RUBRIC_VERSION, GraderDimension


class ClaimFinding(BaseModel):
    """One factual claim extracted from an answer, and whether the supplied
    evidence supports it. Claim extraction is a deterministic heuristic
    (app.evaluation.graders.claims) or a grader-reported finding - neither
    is claimed to be perfect (Section 4's explicit instruction)."""

    model_config = ConfigDict(frozen=True)

    claim_text: str
    cited_evidence_ids: tuple[str, ...] = ()
    supported: bool | None = None  # None = undetermined (not graded, not "unsupported")
    contradicted: bool = False
    unsupported_extension: bool = False
    rationale: str = ""


class CitationFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    citation_index: int
    evidence_id: str
    supports_claim: bool | None = None
    rationale: str = ""


class GraderResult(BaseModel):
    """One dimension's graded outcome for one answer. Matches the shape in
    the task brief's Section 3 example exactly (dimension/score/passed/
    confidence/reason/unsupported_claims/supported_claims/citation_findings/
    rubric_version/prompt_version), plus provenance fields required by
    Section 2 (grader_provider/grader_model) so every stored result can be
    traced back to exactly which model/config produced it."""

    model_config = ConfigDict(frozen=True)

    dimension: GraderDimension
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    unsupported_claims: tuple[str, ...] = ()
    supported_claims: tuple[str, ...] = ()
    citation_findings: tuple[CitationFinding, ...] = ()
    rubric_version: str = RUBRIC_VERSION
    prompt_version: str
    grader_provider: str
    grader_model: str
    is_model_generated_estimate: bool = True  # always True - never claim objective truth (Section "must never claim grader output is objective truth")
    graded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("reason")
    @classmethod
    def _reason_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("reason must not be empty")
        return value


class PairwiseVerdict(BaseModel):
    """A -> baseline/candidate-A, B -> the other side. `order_swapped`
    records whether this particular call presented B first internally (for
    position-bias checking - see engine.py's swapped-order consistency
    check)."""

    model_config = ConfigDict(frozen=True)

    verdict: str = Field(pattern="^(a_better|b_better|tie|both_unacceptable)$")
    reason: str
    rubric_dimension: str
    order_swapped: bool = False
    grader_provider: str
    grader_model: str
    prompt_version: str
    is_model_generated_estimate: bool = True


class ConsistencyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: GraderDimension
    repetitions: int
    scores: tuple[float, ...]
    agreement_rate: float  # fraction of repetitions whose `passed` matches the majority verdict
    score_variance: float
    is_consistent: bool  # see engine.py's _CONSISTENCY_VARIANCE_THRESHOLD
