"""EvidenceSufficiencyVerifier: a deterministic, multi-signal replacement for
`grounding.py`'s single "does one chunk contain every distinctive term"
check, built to close the specific failure mode that check could not:
a chunk that coincidentally contains every extracted term, in unrelated
sentences, about a different fact than the one requested.

Signals combined (see docs/04_Engineering/Similar_But_Absent_Five_Case_Baseline.md
and Evidence_Sufficiency_Design.md for the evidence this design is based on):

1. Requested-fact extraction from the question: entities (proper nouns /
   qualifiers, reusing grounding.extract_distinctive_terms), an expected
   value type (numeric/currency/date/duration/location/contact/eligibility/
   policy_condition/product/procedure), and a domain-relevance signal.
2. Sentence-level proximity: entities and a value of the expected type must
   co-occur within a small sentence window of the SAME chunk, not just
   anywhere in the chunk or scattered across chunks. This is what actually
   distinguishes "Starter" appearing in a sentence about pricing from
   "Starter" appearing in a sentence about retention.
3. Retrieval-confidence-based domain relevance: when a question has no
   extractable entity or attribute AND the best retrieval similarity score is
   below a threshold calibrated against this project's real passing/failing
   cases (see the design doc), the question is treated as off-topic.
4. A structured, explainable outcome per chunk (direct_support /
   nearby_but_incomplete / topic_match_only / attribute_missing /
   relation_missing / value_missing / conflicting_support / off_topic /
   insufficient_evidence) and a single top-level reason code - no opaque
   weighted score.

Explicitly not a claim of perfect fact-checking: value-type detection is
regex-based and entity extraction is a proper-noun/qualifier heuristic (see
grounding.py). Two independent weak signals are required to reject a
question as off-topic (no entity/attribute AND weak retrieval score) so a
single miss cannot false-block a benign question - see the false-positive
analysis in Evidence_Sufficiency_Design.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.ai.guardrails.grounding import extract_distinctive_terms
from app.ai.guardrails.reason_codes import GuardrailReasonCode

SAFE_MESSAGE_REQUESTED_FACT_ABSENT = (
    "The available knowledge base doesn't contain that specific detail. "
    "I found related information, but not the exact fact you asked about."
)
SAFE_MESSAGE_OFF_TOPIC = "That question doesn't appear to relate to the available knowledge base. I can only answer questions about the configured knowledge base."
SAFE_MESSAGE_CONFLICTING = "The knowledge base contains conflicting information for that question, so I can't give a single confident answer."

_MAX_ENTITIES_TO_CHECK = 3  # mirrors grounding.py's noise-avoidance cap
_OFF_TOPIC_SCORE_THRESHOLD = 0.30  # calibrated below the lowest observed top-1 score (0.314) among real passing cases in this project's golden dataset - see design doc
_PROXIMITY_WINDOW = 1  # sentences on each side of a matching sentence considered part of the same "local" evidence window

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ExpectedValueType(str, Enum):
    NUMERIC = "numeric"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    DURATION = "duration"
    LOCATION = "location"
    CONTACT = "contact"
    ELIGIBILITY = "eligibility"
    POLICY_CONDITION = "policy_condition"
    PRODUCT = "product"
    PROCEDURE = "procedure"


# Ordered by specificity - the first matching pattern wins, so more specific
# triggers (currency, duration) are checked before generic ones (numeric).
_VALUE_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], ExpectedValueType], ...] = (
    (re.compile(r"(?i)\bhow much\b|\bprice\b|\bcost\b|\bfee\b|\bcharge\b|\bdiscount\b|\brefund\b.{0,15}\bamount\b"), ExpectedValueType.CURRENCY),
    (re.compile(r"(?i)\bpercent(age)?\b|%"), ExpectedValueType.PERCENTAGE),
    (re.compile(r"(?i)\bwhen\b|\bdeadline\b|\bwhat date\b|\bby what date\b|\brenew(s|al)?\b"), ExpectedValueType.DATE),
    (re.compile(r"(?i)\bhow long\b|\bhow many days\b|\bhow many months\b|\bhow many years\b|\bretention\b|\bexpir(e|es|y)\b|\bresponse time\b|\bsla\b"), ExpectedValueType.DURATION),
    (re.compile(r"(?i)\bwhere\b|\blocated\b|\blocation\b|\bregion\b|\bdata center\b|\bdatacent(er|re)\b"), ExpectedValueType.LOCATION),
    (re.compile(r"(?i)\bwho\b.{0,20}\bcontact\b|\bphone\b|\bemail\b|\bcontact (details|information|number)\b"), ExpectedValueType.CONTACT),
    (re.compile(r"(?i)\beligib(le|ility)\b|\bqualify\b|\brequirement(s)? to\b|\bwho (can|is able to)\b"), ExpectedValueType.ELIGIBILITY),
    (re.compile(r"(?i)\bwhat conditions?\b|\bpolicy\b|\brule(s)?\b|\bwhat happens if\b"), ExpectedValueType.POLICY_CONDITION),
    (re.compile(r"(?i)\bwhich plan\b|\bwhich (product|tier)\b"), ExpectedValueType.PRODUCT),
    (re.compile(r"(?i)\bhow do i\b|\bwhat steps?\b|\bprocess for\b|\bhow can i\b"), ExpectedValueType.PROCEDURE),
    (re.compile(r"(?i)\bhow many\b|\bnumber of\b|\brate limit\b|\blimit\b"), ExpectedValueType.NUMERIC),
)

_WORD_NUMBERS = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty"

_VALUE_EXTRACTORS: dict[ExpectedValueType, re.Pattern[str]] = {
    # "How much"/"discount" questions are ambiguous between a dollar figure and a
    # percentage (e.g. "saves 20% compared to paying monthly") - both count as
    # satisfying evidence for a CURRENCY-typed question.
    ExpectedValueType.CURRENCY: re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|usd)\b|\b\d+(?:\.\d+)?\s?%", re.IGNORECASE),
    ExpectedValueType.PERCENTAGE: re.compile(r"\b\d+(?:\.\d+)?\s?%"),
    ExpectedValueType.DATE: re.compile(
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?\b"
        r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
        # Relative/recurring date descriptions ("on the anniversary of signup", "each
        # month") are common in policy documents and are legitimate evidence for a
        # "when" question even without an absolute calendar date.
        r"|\banniversary\b|\brenewal date\b|\bbilling date\b|\bsignup date\b|\beach (?:month|year)\b|\bevery (?:month|year)\b",
        re.IGNORECASE,
    ),
    ExpectedValueType.DURATION: re.compile(rf"\b(?:\d+(?:\.\d+)?|{_WORD_NUMBERS})[\s-]?(?:day|days|month|months|year|years|hour|hours|minute|minutes|week|weeks)\b", re.IGNORECASE),
    ExpectedValueType.LOCATION: re.compile(r"\b[A-Z][a-zA-Z]+(?:,\s*[A-Z]{2})?\b"),
    ExpectedValueType.CONTACT: re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\b\+?\d[\d\s().-]{7,}\d\b"),
    ExpectedValueType.ELIGIBILITY: re.compile(r"(?i)\b(must|required|only if|eligible|qualifies?|available to)\b"),
    ExpectedValueType.POLICY_CONDITION: re.compile(r"(?i)\b(policy|rule|requires?|applies|subject to|covered by)\b"),
    ExpectedValueType.PRODUCT: re.compile(r"\b(Starter|Team|Business|Enterprise)\b"),
    ExpectedValueType.PROCEDURE: re.compile(r"(?i)\b(step \d|first,|then,|next,|finally,|submit|navigate to|go to|click)\b"),
}

# NUMERIC is deliberately not a static pattern in _VALUE_EXTRACTORS: a bare
# digit is satisfied by any incidental number nearby (a version string like
# "v2.3", an hour range like "24/7") which is not evidence of the specific
# quantity requested. A number only counts if a quantity-unit word appears
# shortly after it in the same sentence - see _extract_numeric_values.
_BARE_NUMBER = re.compile(rf"\b(?:\d+(?:\.\d+)?|{_WORD_NUMBERS})\b", re.IGNORECASE)
_NUMERIC_UNIT_HINT = re.compile(r"(?i)\b(requests?|calls?|times?|codes?|characters?|attempts?|allowance|per\s+(?:minute|second|hour|day|request|call))\b")


def _extract_numeric_values(text: str) -> list[str]:
    matches = []
    for match in _BARE_NUMBER.finditer(text):
        tail = text[match.end(): match.end() + 40]
        if _NUMERIC_UNIT_HINT.search(tail):
            matches.append(match.group())
    return matches

# Attribute types precise enough that two genuinely different values found for
# the same entity are worth flagging as conflicting_evidence. NUMERIC is
# deliberately excluded - policy documents routinely enumerate several related
# numbers for different sub-items in adjacent sentences (e.g. per-tier rate
# limits), which is normal document structure, not a real conflict.
_CONFLICT_ELIGIBLE_TYPES = frozenset({ExpectedValueType.CURRENCY, ExpectedValueType.PERCENTAGE, ExpectedValueType.DATE, ExpectedValueType.DURATION})


_KEYWORD_STOPWORDS = frozenset({
    "what", "when", "where", "how", "does", "do", "did", "is", "are", "was", "were", "the", "for", "and", "with",
    "that", "this", "have", "has", "long", "much", "many", "can", "you", "your", "will", "would", "should", "could",
    "about", "from", "there", "their", "into", "over", "under", "before", "after", "just", "like", "please", "tell",
})


def _topic_keywords(question: str) -> tuple[str, ...]:
    words = re.findall(r"[A-Za-z]{4,}", question.lower())
    return tuple(dict.fromkeys(word for word in words if word not in _KEYWORD_STOPWORDS))


@dataclass(frozen=True)
class RequestedFact:
    entities: tuple[str, ...]
    attribute_type: ExpectedValueType | None
    off_topic_likely: bool
    topic_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkSupportOutcome:
    outcome: str
    matched_sentence: str | None
    matched_value: str | None = None


@dataclass(frozen=True)
class EvidenceSufficiencyVerdict:
    sufficient: bool
    reason_code: GuardrailReasonCode
    requested_fact: RequestedFact
    chunk_outcomes: tuple[str, ...]
    safe_message: str | None = None



# Qualifier-root entities (see grounding.py) that name a *duration unit*
# ("month", "week", "quarter", "annual"/"year") are degenerate as an anchor
# for a DURATION-typed question: almost any duration value expressed in that
# same unit ("24 months") trivially satisfies both the entity and the value
# check simultaneously, even when they describe an unrelated fact. Fall back
# to lexical keyword anchoring in that specific case instead.
_DURATION_UNIT_ENTITY_ROOTS = frozenset({"annual", "month", "quarter", "week", "year"})


def extract_requested_fact(question: str, *, best_retrieval_score: float | None = None) -> RequestedFact:
    entities = extract_distinctive_terms(question)[:_MAX_ENTITIES_TO_CHECK]
    attribute_type = _detect_value_type(question)
    if entities and attribute_type == ExpectedValueType.DURATION and set(entities) <= _DURATION_UNIT_ENTITY_ROOTS:
        entities = ()
    off_topic_likely = (
        not entities
        and attribute_type is None
        and best_retrieval_score is not None
        and best_retrieval_score < _OFF_TOPIC_SCORE_THRESHOLD
    )
    topic_keywords = _topic_keywords(question) if not entities else ()
    return RequestedFact(entities=entities, attribute_type=attribute_type, off_topic_likely=off_topic_likely, topic_keywords=topic_keywords)


def _detect_value_type(question: str) -> ExpectedValueType | None:
    for pattern, value_type in _VALUE_TYPE_PATTERNS:
        if pattern.search(question):
            return value_type
    return None


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text.strip()) if s]


def extract_values(text: str, value_type: ExpectedValueType) -> list[str]:
    if value_type == ExpectedValueType.NUMERIC:
        return _extract_numeric_values(text)
    pattern = _VALUE_EXTRACTORS.get(value_type)
    if pattern is None:
        return []
    return pattern.findall(text)


_MIN_KEYWORD_MATCHES = 2  # requires at least two independent lexical hits, not one coincidental substring match, when there is no proper-noun entity anchor


def evaluate_chunk_support(requested: RequestedFact, chunk_content: str, chunk_title: str, *, proximity_window: int = _PROXIMITY_WINDOW) -> ChunkSupportOutcome:
    sentences = split_sentences(chunk_content)

    if not requested.entities and requested.attribute_type is None:
        return ChunkSupportOutcome(outcome="direct_support", matched_sentence=None)

    # Whether to fold the chunk/document title into each window's anchor
    # check. Meaningful for entity anchors (e.g. a "per the X document"
    # citation-style question naming the document itself) but not for the
    # generic lexical-keyword fallback, where a title word like "Policy" or
    # "Plans" would coincidentally count as a keyword hit on every single
    # sentence of that document regardless of actual relevance.
    include_title = bool(requested.entities)

    if not requested.entities:
        # No proper-noun/qualifier entity to anchor on (common for plainly-phrased
        # questions like "how long is a password reset link valid for?") - fall
        # back to lexical keyword overlap as the anchor. Requires >=2 independent
        # keyword hits (not one coincidental substring match) so a single weak,
        # generic word shared with an unrelated document cannot anchor a match.
        keywords = requested.topic_keywords
        # Short keyword sets (a plainly-phrased, short question) require only
        # one hit - with few keywords, a single real match is already
        # meaningful overlap. Longer keyword sets (a chatty/compound
        # question) require two, since one shared word is more likely to be
        # coincidental when there were many candidate words to begin with.
        required_hits = 1 if len(keywords) <= 3 else _MIN_KEYWORD_MATCHES

        def anchor_present(text: str) -> bool:
            if not keywords:
                return True
            return sum(1 for keyword in keywords if keyword in text) >= required_hits
    else:
        def anchor_present(text: str) -> bool:
            return all(term.lower() in text for term in requested.entities)

    # Pass 1: entity/keyword anchor and the requested value must appear in the
    # SAME sentence - this is what actually distinguishes "the fact this
    # question asks about" from "a coincidentally nearby but unrelated fact"
    # (see Guardrails_Task_Specification.md and the multi-case false-positive
    # analysis this design is based on).
    for sentence in sentences:
        lowered = f"{sentence} {chunk_title}".lower() if include_title else sentence.lower()
        if not anchor_present(lowered):
            continue
        if requested.attribute_type is None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentence)
        values = extract_values(lowered, requested.attribute_type)
        if values:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentence, matched_value=values[0])

    # Pass 2: anchor (and value, if a value type is requested) co-occur within
    # a wider sentence window rather than one sentence - still direct support,
    # since a fact and its qualifying detail are often split across adjacent
    # sentences in prose (e.g. two tiers' support hours described one
    # sentence apart).
    for index in range(len(sentences)):
        window = " ".join(sentences[max(0, index - proximity_window): index + proximity_window + 1])
        window_lower = f"{window} {chunk_title}".lower() if include_title else window.lower()
        if not anchor_present(window_lower):
            continue
        if requested.attribute_type is None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentences[index])
        values = extract_values(window_lower, requested.attribute_type)
        if values:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentences[index], matched_value=values[0])

    whole_text = f"{chunk_content} {chunk_title}".lower() if include_title else chunk_content.lower()

    if not requested.entities:
        keywords = requested.topic_keywords
        if not keywords:
            return ChunkSupportOutcome(outcome="insufficient_evidence", matched_sentence=None)
        hits = sum(1 for keyword in keywords if keyword in whole_text)
        required_hits = 1 if len(keywords) <= 3 else _MIN_KEYWORD_MATCHES
        if hits >= required_hits:
            return ChunkSupportOutcome(outcome="value_missing" if requested.attribute_type else "topic_match_only", matched_sentence=None)
        if hits:
            return ChunkSupportOutcome(outcome="topic_match_only", matched_sentence=None)
        return ChunkSupportOutcome(outcome="insufficient_evidence", matched_sentence=None)

    entities_anywhere = [term for term in requested.entities if term.lower() in whole_text]
    if len(entities_anywhere) == len(requested.entities):
        if requested.attribute_type is not None:
            return ChunkSupportOutcome(outcome="value_missing", matched_sentence=None)
        return ChunkSupportOutcome(outcome="nearby_but_incomplete", matched_sentence=None)
    if entities_anywhere:
        return ChunkSupportOutcome(outcome="topic_match_only", matched_sentence=None)
    return ChunkSupportOutcome(outcome="insufficient_evidence", matched_sentence=None)


def verify_evidence_sufficiency(
    *,
    question: str,
    chunk_contents: list[str],
    chunk_titles: list[str] | None = None,
    retrieval_scores: list[float] | None = None,
) -> EvidenceSufficiencyVerdict:
    best_score = max(retrieval_scores) if retrieval_scores else None
    requested = extract_requested_fact(question, best_retrieval_score=best_score)

    if requested.off_topic_likely:
        return EvidenceSufficiencyVerdict(
            sufficient=False, reason_code=GuardrailReasonCode.RELATED_TOPIC_ONLY, requested_fact=requested,
            chunk_outcomes=("off_topic",), safe_message=SAFE_MESSAGE_OFF_TOPIC,
        )

    if not chunk_contents:
        return EvidenceSufficiencyVerdict(
            sufficient=False, reason_code=GuardrailReasonCode.NO_AUTHORISED_EVIDENCE, requested_fact=requested,
            chunk_outcomes=(), safe_message=SAFE_MESSAGE_REQUESTED_FACT_ABSENT,
        )

    if not requested.entities and requested.attribute_type is None:
        # No specific fact to verify (and not flagged off-topic above) - nothing to check, matches grounding.py's existing pass-through behaviour.
        return EvidenceSufficiencyVerdict(
            sufficient=True, reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE, requested_fact=requested,
            chunk_outcomes=(), safe_message=None,
        )

    titles = chunk_titles or [""] * len(chunk_contents)
    outcomes = [evaluate_chunk_support(requested, content, title) for content, title in zip(chunk_contents, titles)]
    outcome_labels = tuple(o.outcome for o in outcomes)

    if any(label == "direct_support" for label in outcome_labels):
        if requested.attribute_type in _CONFLICT_ELIGIBLE_TYPES:
            supporting_values = {o.matched_value for o in outcomes if o.outcome == "direct_support" and o.matched_value}
            if len(supporting_values) > 1:
                return EvidenceSufficiencyVerdict(
                    sufficient=False, reason_code=GuardrailReasonCode.CONFLICTING_EVIDENCE, requested_fact=requested,
                    chunk_outcomes=outcome_labels, safe_message=SAFE_MESSAGE_CONFLICTING,
                )
        return EvidenceSufficiencyVerdict(
            sufficient=True, reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE, requested_fact=requested,
            chunk_outcomes=outcome_labels, safe_message=None,
        )

    return EvidenceSufficiencyVerdict(
        sufficient=False, reason_code=GuardrailReasonCode.REQUESTED_FACT_ABSENT, requested_fact=requested,
        chunk_outcomes=outcome_labels, safe_message=SAFE_MESSAGE_REQUESTED_FACT_ABSENT,
    )
