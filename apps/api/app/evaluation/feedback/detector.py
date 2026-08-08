"""Scans existing production data (ChatMessage/AITrace/AIGuardrailTrace/
AIModelCallTrace - no new production-side instrumentation required) for
failure signals and turns them into EvaluationCandidate rows via the
repository, redacting content first.

Deliberately does not treat every fallback as a defect: a signal only creates
a *new* candidate row on first occurrence when its type is in
SEVERE_ON_FIRST_OCCURRENCE; otherwise the first occurrence is recorded but
only surfaces as a candidate once it recurs (a second matching signal bumps
the existing unresolved candidate's occurrence_count instead of creating a
new row - see repository.create_or_bump_candidate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIGuardrailTrace, AIModelCallTrace, AITrace, ChatMessage, Citation
from app.evaluation.feedback.dedup import compute_dedup_hash
from app.evaluation.feedback.signals import SignalType
from app.evaluation.policy import EvaluationPolicy, load_policy_from_env
from app.repositories import evaluation_candidate_repository

_ANSWER_STATE_SIGNALS: dict[str, SignalType] = {
    "fallback": SignalType.FALLBACK,
    "low_confidence": SignalType.LOW_CONFIDENCE,
}


@dataclass(frozen=True)
class CandidateDraft:
    organisation_id: str
    workspace_id: str
    widget_id: str
    signal_type: SignalType
    severity: str
    question: str
    response: str | None
    reason_code: str
    source_trace_id: str | None = None
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    evidence_refs: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DetectionSummary:
    scanned_signals: int
    candidates_created: int
    candidates_bumped: int


def _preceding_user_question(db: Session, *, conversation_id: str, before_sequence: int | None, organisation_id: str, workspace_id: str) -> str | None:
    statement = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.role == "user",
    )
    if before_sequence is not None:
        statement = statement.where(ChatMessage.sequence_number < before_sequence)
    statement = statement.order_by(ChatMessage.sequence_number.desc()).limit(1)
    row = db.execute(statement).scalar_one_or_none()
    return row.content if row is not None else None


def _evidence_refs_for_message(db: Session, *, message_id: str, organisation_id: str, workspace_id: str) -> list[dict]:
    statement = select(Citation).where(
        Citation.message_id == message_id,
        Citation.organisation_id == organisation_id,
        Citation.workspace_id == workspace_id,
    )
    return [
        {"document_id": citation.document_id, "chunk_id": citation.chunk_id, "source_title": citation.source_title}
        for citation in db.execute(statement).scalars().all()
    ]


def _scan_answer_state_signals(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, since: datetime) -> list[CandidateDraft]:
    statement = select(ChatMessage).where(
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.widget_id == widget_id,
        ChatMessage.role == "assistant",
        ChatMessage.answer_state.in_(tuple(_ANSWER_STATE_SIGNALS)),
        ChatMessage.created_at >= since,
    )
    drafts: list[CandidateDraft] = []
    for message in db.execute(statement).scalars().all():
        question = _preceding_user_question(
            db, conversation_id=message.conversation_id, before_sequence=message.sequence_number, organisation_id=organisation_id, workspace_id=workspace_id
        )
        if not question:
            continue
        signal_type = _ANSWER_STATE_SIGNALS[message.answer_state]
        drafts.append(
            CandidateDraft(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                signal_type=signal_type,
                severity="medium",
                question=question,
                response=message.content,
                reason_code=message.answer_state,
                source_conversation_id=message.conversation_id,
                source_message_id=message.id,
                metadata={"error_code": message.error_code},
            )
        )
    return drafts


def _scan_missing_citation_signals(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, since: datetime) -> list[CandidateDraft]:
    citation_count = (
        select(Citation.id)
        .where(
            Citation.organisation_id == organisation_id,
            Citation.workspace_id == workspace_id,
            Citation.message_id == ChatMessage.id,
        )
        .correlate(ChatMessage)
        .exists()
    )
    statement = select(ChatMessage).where(
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.widget_id == widget_id,
        ChatMessage.role == "assistant",
        ChatMessage.answer_state.is_(None),
        ChatMessage.created_at >= since,
        ~citation_count,
    )
    drafts: list[CandidateDraft] = []
    for message in db.execute(statement).scalars().all():
        question = _preceding_user_question(
            db, conversation_id=message.conversation_id, before_sequence=message.sequence_number, organisation_id=organisation_id, workspace_id=workspace_id
        )
        if not question:
            continue
        drafts.append(
            CandidateDraft(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                signal_type=SignalType.MISSING_CITATION,
                severity="medium",
                question=question,
                response=message.content,
                reason_code="missing_citation",
                source_conversation_id=message.conversation_id,
                source_message_id=message.id,
            )
        )
    return drafts


def _scan_guardrail_signals(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, since: datetime) -> list[CandidateDraft]:
    statement = (
        select(AIGuardrailTrace, AITrace)
        .join(AITrace, AITrace.id == AIGuardrailTrace.trace_id)
        .where(
            AIGuardrailTrace.organisation_id == organisation_id,
            AIGuardrailTrace.workspace_id == workspace_id,
            AITrace.assistant_id == widget_id,
            AIGuardrailTrace.blocked.is_(True),
            AIGuardrailTrace.created_at >= since,
        )
    )
    drafts: list[CandidateDraft] = []
    for guardrail_trace, trace in db.execute(statement).all():
        question = None
        if trace.conversation_id:
            question = _preceding_user_question(
                db, conversation_id=trace.conversation_id, before_sequence=None, organisation_id=organisation_id, workspace_id=workspace_id
            )
        if not question:
            continue
        drafts.append(
            CandidateDraft(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                signal_type=SignalType.GUARDRAIL_TRIGGER,
                severity="high",
                question=question,
                response=None,
                reason_code=guardrail_trace.reason_code or guardrail_trace.guardrail_name,
                source_trace_id=trace.id,
                source_conversation_id=trace.conversation_id,
                metadata={"guardrail_name": guardrail_trace.guardrail_name, "layer": guardrail_trace.layer},
            )
        )
    return drafts


def _scan_provider_failure_signals(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, since: datetime) -> list[CandidateDraft]:
    statement = (
        select(AIModelCallTrace, AITrace)
        .join(AITrace, AITrace.id == AIModelCallTrace.trace_id)
        .where(
            AIModelCallTrace.organisation_id == organisation_id,
            AIModelCallTrace.workspace_id == workspace_id,
            AITrace.assistant_id == widget_id,
            AIModelCallTrace.outcome != "success",
            AIModelCallTrace.created_at >= since,
        )
    )
    drafts: list[CandidateDraft] = []
    for call_trace, trace in db.execute(statement).all():
        question = None
        if trace.conversation_id:
            question = _preceding_user_question(
                db, conversation_id=trace.conversation_id, before_sequence=None, organisation_id=organisation_id, workspace_id=workspace_id
            )
        if not question:
            continue
        drafts.append(
            CandidateDraft(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                signal_type=SignalType.PROVIDER_FAILURE,
                severity="high",
                question=question,
                response=None,
                reason_code=call_trace.error_code or call_trace.outcome,
                source_trace_id=trace.id,
                source_conversation_id=trace.conversation_id,
                metadata={"provider_key": call_trace.provider_key, "outcome": call_trace.outcome},
            )
        )
    return drafts


def _scan_high_latency_signals(
    db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, since: datetime, policy: EvaluationPolicy
) -> list[CandidateDraft]:
    statement = select(AITrace).where(
        AITrace.organisation_id == organisation_id,
        AITrace.workspace_id == workspace_id,
        AITrace.assistant_id == widget_id,
        AITrace.total_latency_ms.isnot(None),
        AITrace.total_latency_ms > policy.max_p95_latency_ms,
        AITrace.created_at >= since,
    )
    drafts: list[CandidateDraft] = []
    for trace in db.execute(statement).scalars().all():
        question = None
        if trace.conversation_id:
            question = _preceding_user_question(
                db, conversation_id=trace.conversation_id, before_sequence=None, organisation_id=organisation_id, workspace_id=workspace_id
            )
        if not question:
            continue
        drafts.append(
            CandidateDraft(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                signal_type=SignalType.HIGH_LATENCY,
                severity="low",
                question=question,
                response=None,
                reason_code="high_latency",
                source_trace_id=trace.id,
                source_conversation_id=trace.conversation_id,
                metadata={"total_latency_ms": trace.total_latency_ms, "threshold_ms": policy.max_p95_latency_ms},
            )
        )
    return drafts


def scan_for_candidates(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    since: datetime | None = None,
    policy: EvaluationPolicy | None = None,
    dry_run: bool = False,
) -> DetectionSummary:
    since = since or datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    policy = policy or load_policy_from_env()

    drafts: list[CandidateDraft] = [
        *_scan_answer_state_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, since=since),
        *_scan_missing_citation_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, since=since),
        *_scan_guardrail_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, since=since),
        *_scan_provider_failure_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, since=since),
        *_scan_high_latency_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, since=since, policy=policy),
    ]

    created = bumped = 0
    for draft in drafts:
        if dry_run:
            # Read-only preview - never writes, so there is nothing to roll
            # back afterwards (repository writes below commit per-candidate,
            # which a session-level rollback cannot undo after the fact).
            dedup_hash = compute_dedup_hash(draft.question, widget_id=draft.widget_id, reason_code=draft.reason_code)
            outcome_kind = evaluation_candidate_repository.preview_dedup_outcome(
                db, organisation_id=draft.organisation_id, workspace_id=draft.workspace_id, dedup_hash=dedup_hash
            )
            created += 1 if outcome_kind == "create" else 0
            bumped += 1 if outcome_kind == "bump" else 0
            continue

        outcome = evaluation_candidate_repository.create_or_bump_candidate(
            db,
            organisation_id=draft.organisation_id,
            workspace_id=draft.workspace_id,
            widget_id=draft.widget_id,
            signal_type=draft.signal_type.value,
            severity=draft.severity,
            question=draft.question,
            response=draft.response,
            reason_code=draft.reason_code,
            source_trace_id=draft.source_trace_id,
            source_conversation_id=draft.source_conversation_id,
            source_message_id=draft.source_message_id,
            evidence_refs=draft.evidence_refs
            or (
                _evidence_refs_for_message(db, message_id=draft.source_message_id, organisation_id=draft.organisation_id, workspace_id=draft.workspace_id)
                if draft.source_message_id
                else []
            ),
            metadata=draft.metadata,
        )
        if outcome.created:
            created += 1
        elif outcome.bumped:
            bumped += 1

    return DetectionSummary(scanned_signals=len(drafts), candidates_created=created, candidates_bumped=bumped)
