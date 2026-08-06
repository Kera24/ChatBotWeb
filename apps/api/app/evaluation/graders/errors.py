"""Error hierarchy for the grader subsystem - deliberately separate from
app.ai.errors (the live-request AI provider hierarchy) and mirrors the
existing app.services.embeddings error pattern (a small, flat hierarchy of
plain exceptions), since graders are an evaluation-time tool, not part of
the live request path.
"""


class GraderProviderError(RuntimeError):
    """Base class for every grader-provider failure."""


class GraderNotConfiguredError(GraderProviderError):
    """Raised when a real (non-mock) grader was requested but its
    configuration is incomplete or points at the mock provider."""


class GraderTimeoutError(GraderProviderError):
    """Raised when a grader call exceeds EVAL_GRADER_TIMEOUT_SECONDS."""


class GraderOutputValidationError(GraderProviderError):
    """Raised when a grader's raw output cannot be parsed into the
    structured GraderResult contract. Callers should catch this and record
    a safe 'malformed output' result rather than letting it propagate and
    abort an entire grading run - see engine.py's per-dimension isolation."""
