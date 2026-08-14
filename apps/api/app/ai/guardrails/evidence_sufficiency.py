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
from typing import Protocol

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
# "v2.3", an hour range like "24/7", a document ID, a phone number) which is
# not evidence of the specific quantity requested. A number only counts if
# either (a) a quantity-unit word appears shortly after it, or (b) it sits in
# a recognisable bound/limit construction - see _extract_numeric_values.
_BARE_NUMBER = re.compile(rf"\b(?:\d+(?:\.\d+)?|{_WORD_NUMBERS})\b", re.IGNORECASE)
_NUMERIC_UNIT_HINT = re.compile(r"(?i)\b(requests?|calls?|times?|codes?|characters?|attempts?|allowance|per\s+(?:minute|second|hour|day|request|call))\b")

# Bound/limit qualifiers that anchor a number as a genuine quantity regardless
# of the noun it counts ("a maximum of 25 matrix combinations", "no more than
# 25 items") - the general fix for the numeric-value-extraction defect where
# only a small closed vocabulary of unit-hint nouns was recognised. Anchored
# to the end of the preceding context window with \s*$ so the qualifier must
# immediately precede the number (not merely appear somewhere earlier in the
# sentence, which would risk anchoring on an unrelated quantity).
_NUMERIC_QUALIFIER_BEFORE = re.compile(
    r"(?i)\b(?:maximum|minimum|max|min)\s+of\s*$"
    r"|\bup\s+to\s*$"
    r"|\bno\s+more\s+than\s*$|\bnot\s+more\s+than\s*$"
    r"|\bno\s+fewer\s+than\s*$|\bno\s+less\s+than\s*$"
    r"|\bat\s+least\s*$|\bat\s+most\s*$"
    r"|\bcapped\s+at\s*$"
    r"|\blimit(?:ed)?\s+to\s*$|\blimit\s+is\s*$|\blimit\s+of\s*$"
    r"|\bno\s+greater\s+than\s*$|\bnot\s+to\s+exceed\s*$|\bnot\s+exceed(?:ing)?\s*$"
    r"|\bbetween\s*$"
)
# Bound/limit qualifiers that follow the number ("25 combinations maximum",
# "3 or more reviewers"), bounded to a short trailing window like
# _NUMERIC_UNIT_HINT to avoid anchoring on a qualifier that belongs to a
# later, unrelated number.
_NUMERIC_QUALIFIER_AFTER = re.compile(r"(?i)\b(maximum|minimum|max|min|or\s+(?:fewer|more|less|greater))\b")

# A number immediately preceded by a version marker ("v2.3", "version 3",
# "ver. 3") is a version identifier, not a quantity - this must be checked
# before, and take precedence over, any qualifier match above, since an
# adversarial construction like "supported up to version 3" would otherwise
# be misread as a bound on a quantity of 3.
_VERSION_MARKER_BEFORE = re.compile(r"(?i)\bv(?:er(?:sion)?)?\.?\s*$")

# "between 3 and 10": the first number is caught by _NUMERIC_QUALIFIER_BEFORE
# ("between"), but the second number's only local anchor is the word "and",
# which is too generic to treat as a qualifier on its own (would false-anchor
# on unrelated adjacent numbers). Extracted explicitly as a pair instead.
_NUMERIC_RANGE = re.compile(rf"(?i)\bbetween\s+(\d+(?:\.\d+)?|{_WORD_NUMBERS})\s+and\s+(\d+(?:\.\d+)?|{_WORD_NUMBERS})\b")

_NUMERIC_CONTEXT_WINDOW = 35


def _extract_numeric_values(text: str) -> list[str]:
    matches = []
    for match in _BARE_NUMBER.finditer(text):
        before = text[max(0, match.start() - _NUMERIC_CONTEXT_WINDOW): match.start()]
        if _VERSION_MARKER_BEFORE.search(before):
            continue
        after = text[match.end(): match.end() + 40]
        if _NUMERIC_UNIT_HINT.search(after) or _NUMERIC_QUALIFIER_BEFORE.search(before) or _NUMERIC_QUALIFIER_AFTER.search(after):
            matches.append(match.group())
    for range_match in _NUMERIC_RANGE.finditer(text):
        matches.append(range_match.group(1))
        matches.append(range_match.group(2))
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
    # Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md) -
    # the full per-chunk ChunkSupportOutcome (matched_value/matched_sentence),
    # not just the outcome label chunk_outcomes already carries. Defaults to
    # `()` and is populated ONLY by verify_evidence_sufficiency_v2 below -
    # verify_evidence_sufficiency (V1) never sets it, so every V1 caller/test
    # keeps producing byte-identical verdicts. Positionally aligned with
    # chunk_outcomes/the original chunk_contents list when present.
    chunk_support_details: tuple[ChunkSupportOutcome, ...] = ()



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


# ============================================================================
# Evidence Sufficiency V2 - additive, evidence-driven fixes to specific false-
# rejection mechanisms proven against the real corpus by
# app.operations.eval_evidence_sufficiency_failure_analysis (--real, both
# golden_dataset.json and chunking_dataset.json, nomic-embed-text-v2-moe,
# threshold 0.32). Everything above this line (V1) is completely unmodified -
# every existing call site/test keeps its exact current behaviour. V2 is
# opt-in via build_evidence_verifier()/settings.EVIDENCE_VERIFIER_VERSION,
# defaulting to "v1" in production until promoted (see the promotion report
# this task produced).
#
# Concrete, reproduced root causes fixed here (case IDs and raw
# retrieved-chunk evidence live in the promotion report, not repeated here -
# "do not infer a category without inspecting retrieved evidence"):
#
#   1. Case-sensitivity bug: `evaluate_chunk_support` above extracts values
#      from an ALREADY-LOWERCASED window, which silently defeats any pattern
#      requiring an uppercase first letter - LOCATION's `[A-Z][a-zA-Z]+`
#      could never match a real city/region name, ever, regardless of
#      whether it was actually present in the retrieved chunk (100% of
#      LOCATION-typed questions in the failure analysis were false
#      rejections for exactly this reason). V2 extracts against the
#      ORIGINAL-case window text; anchor matching stays case-insensitive.
#   2. First-match bug: V1 takes `values[0]`, the first value anywhere in the
#      anchor window, even when several typed values appear in the same
#      window - a markdown pricing table with no terminal punctuation
#      collapses into one "sentence", so a question about the Team plan's
#      price could silently be attributed the Starter row's price instead.
#      V2 splits markdown table rows as their own sentence-like unit AND
#      picks the value positioned nearest the matched anchor, not merely the
#      first one found in the window.
#   3. Weak-anchor false collision: when a question has no extractable
#      entity, V1's keyword-fallback anchor requires as few as ONE shared
#      generic word (e.g. "days") to treat a chunk as supporting evidence -
#      across multi-section policy documents this repeatedly produced
#      several spurious `direct_support` outcomes with DIFFERENT
#      numeric/duration/currency values for the SAME question, which V1's
#      conflict check then reports as `conflicting_evidence` even though
#      only one of them is the real answer (an "unrelated numeric collision"
#      - not a genuine contradiction, supersession, or scope difference).
#      V2 raises the keyword-hit threshold specifically when a typed value
#      is being verified, since precision matters far more once a specific
#      number/date is about to be asserted as the answer.
#   4. DATE's extraction pattern required a day-of-month ("February 15") and
#      rejected the common "Month YYYY" prose form ("In February 2025,
#      Meridian completed..."). V2 adds that alternative.
#   5. Value-type misdetection: the CONTACT trigger pattern
#      (`\bphone\b|\bemail\b`) fired on plain availability questions ("Is
#      phone support available on the Team tier?"), routing them through a
#      phone-number/email regex that could never match availability prose.
#      V2 requires an explicit contact-detail-seeking frame for CONTACT and
#      routes bare "is/are ... available" phrasing to ELIGIBILITY instead.
#   6. PROCEDURE's trigger pattern missed common escalation/contact-support
#      phrasing ("escalate", "contact the support team") - V2 adds a small,
#      reviewed set of equivalents, not a broad keyword net.
#
# Explicitly NOT changed by V2 (evidence did not support it - "implement X
# only if the failure analysis proves it is needed"): multi-chunk evidence
# composition (only one case across both corpora needed it - see the
# promotion report's Part 3 finding) and a semantic/paraphrase fallback (no
# case's rejection traced to a lexical-only miss once the above were
# accounted for).
# ============================================================================

_LOCATION_VALUE_PATTERN = re.compile(r"\b[A-Z][a-zA-Z]+(?:,\s*[A-Z]{2})?\b")

# DATE V2: adds a "Month YYYY" (no day-of-month) alternative to V1's pattern,
# which required a day. Both alternatives kept case-insensitive at the
# pattern level (re.IGNORECASE) since V2 now extracts from original-case
# text where the month name could be capitalised or not depending on
# position in the sentence.
_DATE_VALUE_PATTERN_V2 = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?\b"
    r"|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\banniversary\b|\brenewal date\b|\bbilling date\b|\bsignup date\b|\beach (?:month|year)\b|\bevery (?:month|year)\b",
    re.IGNORECASE,
)

# PROCEDURE V2: adds escalation/contact-support phrasing observed missing in
# the failure analysis - a small, reviewed extension, not a broad net.
_PROCEDURE_VALUE_PATTERN_V2 = re.compile(
    r"(?i)\b(step \d|first,|then,|next,|finally,|submit|navigate to|go to|click"
    r"|escalates?|escalation|contact (the|your) (support|account) team|open a (ticket|case)|respond(s)? within)\b"
)

_VALUE_EXTRACTORS_V2: dict[ExpectedValueType, re.Pattern[str]] = {
    **_VALUE_EXTRACTORS,
    ExpectedValueType.DATE: _DATE_VALUE_PATTERN_V2,
    ExpectedValueType.LOCATION: _LOCATION_VALUE_PATTERN,
    ExpectedValueType.PROCEDURE: _PROCEDURE_VALUE_PATTERN_V2,
}

# CONTACT V2: narrowed to an explicit ask for contact details (a phone
# number/email address/how-to-reach-someone framing) - fixes 100% of the
# reproduced CONTACT misdetections, which were all plain availability
# questions ("is phone support available") that this bare pattern used to
# swallow. ELIGIBILITY V2 gains the "is/are ... available" framing those
# questions actually are, so they still resolve to a real value type instead
# of falling through to None.
_CONTACT_TRIGGER_V2 = re.compile(r"(?i)\bcontact (details|information|number)\b|\bphone number\b|\bemail address\b|\bhow (do|can) i contact\b|\bwho (do|can) i contact\b|\breach (support|someone|a human)\b")
_ELIGIBILITY_TRIGGER_V2 = re.compile(r"(?i)\beligib(le|ility)\b|\bqualify\b|\brequirement(s)? to\b|\bwho (can|is able to)\b|\bis\b.{0,30}\bavailable\b|\bare\b.{0,30}\bavailable\b")

_VALUE_TYPE_PATTERNS_V2: tuple[tuple[re.Pattern[str], ExpectedValueType], ...] = tuple(
    (_CONTACT_TRIGGER_V2, ExpectedValueType.CONTACT) if value_type == ExpectedValueType.CONTACT
    else (_ELIGIBILITY_TRIGGER_V2, ExpectedValueType.ELIGIBILITY) if value_type == ExpectedValueType.ELIGIBILITY
    else (pattern, value_type)
    for pattern, value_type in _VALUE_TYPE_PATTERNS
)

# Stricter than V1's _MIN_KEYWORD_MATCHES (1-2): once a typed value is about
# to be asserted as the answer, a single coincidentally shared generic word
# is not enough evidence that a chunk describes the SAME fact as the
# question - see root cause 3 above.
_MIN_KEYWORD_MATCHES_TYPED_V2 = 2


def _detect_value_type_v2(question: str) -> ExpectedValueType | None:
    for pattern, value_type in _VALUE_TYPE_PATTERNS_V2:
        if pattern.search(question):
            return value_type
    return None


def split_sentences_v2(text: str) -> list[str]:
    """Like split_sentences, but also splits markdown table rows (lines
    starting with `|`) and bare newlines as their own unit - fixes root
    cause 2 (a whole multi-row table collapsing into one "sentence" because
    it has no terminal punctuation)."""
    units: list[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        units.extend(s for s in _SENTENCE_SPLIT.split(block) if s)
    return units


def extract_values_v2(text: str, value_type: ExpectedValueType) -> list[tuple[str, int]]:
    """Like extract_values, but returns (value, start_index) pairs against
    the given (original-case, for LOCATION correctness) text, so the caller
    can pick the value nearest the matched anchor instead of merely the
    first one found - fixes root cause 1 (case-sensitivity) and enables
    root cause 2's nearest-value selection."""
    if value_type == ExpectedValueType.NUMERIC:
        return [(m, text.find(m)) for m in _extract_numeric_values(text)]
    pattern = _VALUE_EXTRACTORS_V2.get(value_type)
    if pattern is None:
        return []
    return [(match.group(), match.start()) for match in pattern.finditer(text)]


def _anchor_position_v2(window_lower: str, requested: RequestedFact, *, required_hits: int) -> int | None:
    """Position of the anchor match within window_lower, or None if the
    anchor is absent - the entity/keyword-presence check V1's closures made,
    reworked to also report WHERE the anchor matched so extract_values_v2's
    nearest-value selection has something to measure distance from."""
    if requested.entities:
        positions = [window_lower.find(term.lower()) for term in requested.entities]
        if any(pos < 0 for pos in positions):
            return None
        return min(positions)
    keywords = requested.topic_keywords
    if not keywords:
        return 0
    positions = [window_lower.find(keyword) for keyword in keywords if keyword in window_lower]
    if len(positions) < required_hits:
        return None
    return min(positions)


def evaluate_chunk_support_v2(requested: RequestedFact, chunk_content: str, chunk_title: str, *, proximity_window: int = _PROXIMITY_WINDOW) -> ChunkSupportOutcome:
    sentences = split_sentences_v2(chunk_content)

    if not requested.entities and requested.attribute_type is None:
        return ChunkSupportOutcome(outcome="direct_support", matched_sentence=None)

    include_title = bool(requested.entities)
    keywords = requested.topic_keywords
    # Deliberately IDENTICAL to V1's threshold here (root cause 3's stricter
    # bar is applied only at conflict-arbitration time in
    # verify_evidence_sufficiency_v2, not here) - tightening this primary
    # anchor check directly regressed a real single-document paraphrase case
    # ("When does my billing cycle renew?" / "Billing occurs on the
    # anniversary...", only one shared keyword - "billing" - yet the correct
    # and only answer) during the Part 8 bake-off. A weak keyword anchor is a
    # real problem specifically when it lets a SECOND, unrelated value
    # masquerade as a competing answer - not when it is the only evidence
    # found at all.
    required_hits = len(requested.entities) if requested.entities else (1 if len(keywords) <= 3 else _MIN_KEYWORD_MATCHES)

    def find_best(window_original: str, window_lower: str) -> tuple[str | None, str | None]:
        anchor_pos = _anchor_position_v2(window_lower, requested, required_hits=required_hits)
        if anchor_pos is None:
            return None, None
        if requested.attribute_type is None:
            return "matched", None
        candidates = extract_values_v2(window_original, requested.attribute_type)
        if not candidates:
            return None, None
        nearest_value = min(candidates, key=lambda pair: abs(pair[1] - anchor_pos))[0]
        return "matched", nearest_value

    for sentence in sentences:
        original_window = f"{sentence} {chunk_title}" if include_title else sentence
        lowered = original_window.lower()
        matched, value = find_best(original_window, lowered)
        if matched is None:
            continue
        if requested.attribute_type is None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentence)
        if value is not None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentence, matched_value=value)

    for index in range(len(sentences)):
        window = " ".join(sentences[max(0, index - proximity_window): index + proximity_window + 1])
        original_window = f"{window} {chunk_title}" if include_title else window
        lowered = original_window.lower()
        matched, value = find_best(original_window, lowered)
        if matched is None:
            continue
        if requested.attribute_type is None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentences[index])
        if value is not None:
            return ChunkSupportOutcome(outcome="direct_support", matched_sentence=sentences[index], matched_value=value)

    whole_text = f"{chunk_content} {chunk_title}".lower() if include_title else chunk_content.lower()

    if not requested.entities:
        if not keywords:
            return ChunkSupportOutcome(outcome="insufficient_evidence", matched_sentence=None)
        hits = sum(1 for keyword in keywords if keyword in whole_text)
        fallback_required_hits = 1 if len(keywords) <= 3 else _MIN_KEYWORD_MATCHES
        if hits >= fallback_required_hits:
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


def extract_requested_fact_v2(question: str, *, best_retrieval_score: float | None = None) -> RequestedFact:
    entities = extract_distinctive_terms(question)[:_MAX_ENTITIES_TO_CHECK]
    attribute_type = _detect_value_type_v2(question)
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


def verify_evidence_sufficiency_v2(
    *,
    question: str,
    chunk_contents: list[str],
    chunk_titles: list[str] | None = None,
    retrieval_scores: list[float] | None = None,
) -> EvidenceSufficiencyVerdict:
    best_score = max(retrieval_scores) if retrieval_scores else None
    requested = extract_requested_fact_v2(question, best_retrieval_score=best_score)

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
        return EvidenceSufficiencyVerdict(
            sufficient=True, reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE, requested_fact=requested,
            chunk_outcomes=(), safe_message=None,
        )

    titles = chunk_titles or [""] * len(chunk_contents)
    outcomes = [evaluate_chunk_support_v2(requested, content, title) for content, title in zip(chunk_contents, titles)]
    outcome_labels = tuple(o.outcome for o in outcomes)

    if any(label == "direct_support" for label in outcome_labels):
        if requested.attribute_type in _CONFLICT_ELIGIBLE_TYPES:
            supporting = [o for o in outcomes if o.outcome == "direct_support" and o.matched_value]
            if not requested.entities and requested.topic_keywords:
                # Root cause 3, applied ONLY here (conflict arbitration) - a
                # second "supporting" occurrence anchored by just one shared
                # generic word (e.g. "logs" alone matching an unrelated
                # Audit Logs sentence when the question is about Build Logs)
                # is not trustworthy enough to assert a genuine second value
                # for the SAME fact; require the same stricter hit count the
                # primary match would need if it were the only evidence.
                # Never discards the single-answer case - a chunk that
                # doesn't clear this bar just stops counting toward the
                # conflict set, it does not become "insufficient" on its own.
                required = min(_MIN_KEYWORD_MATCHES_TYPED_V2, len(requested.topic_keywords))
                supporting = [
                    o for o in supporting
                    if o.matched_sentence and sum(1 for kw in requested.topic_keywords if kw in o.matched_sentence.lower()) >= required
                ]
            supporting_values = {o.matched_value for o in supporting}
            if len(supporting_values) > 1:
                return EvidenceSufficiencyVerdict(
                    sufficient=False, reason_code=GuardrailReasonCode.CONFLICTING_EVIDENCE, requested_fact=requested,
                    chunk_outcomes=outcome_labels, safe_message=SAFE_MESSAGE_CONFLICTING, chunk_support_details=tuple(outcomes),
                )
        return EvidenceSufficiencyVerdict(
            sufficient=True, reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE, requested_fact=requested,
            chunk_outcomes=outcome_labels, safe_message=None, chunk_support_details=tuple(outcomes),
        )

    return EvidenceSufficiencyVerdict(
        sufficient=False, reason_code=GuardrailReasonCode.REQUESTED_FACT_ABSENT, requested_fact=requested,
        chunk_outcomes=outcome_labels, safe_message=SAFE_MESSAGE_REQUESTED_FACT_ABSENT, chunk_support_details=tuple(outcomes),
    )


class EvidenceVerifier(Protocol):
    """Injectable evidence-sufficiency verifier - mirrors
    app.services.reranking.Reranker / app.services.query_transformation.QueryTransformer's
    exact pattern (a `version`/provider identity attribute + one call
    method) so RAGOrchestrator and the evaluation engine can swap V1/V2
    without any change to the pipeline's control flow."""

    version: str

    def verify(
        self, *, question: str, chunk_contents: list[str], chunk_titles: list[str] | None = None, retrieval_scores: list[float] | None = None,
    ) -> EvidenceSufficiencyVerdict: ...


@dataclass(frozen=True)
class EvidenceSufficiencyV1Verifier:
    version: str = "v1"

    def verify(self, **kwargs) -> EvidenceSufficiencyVerdict:
        return verify_evidence_sufficiency(**kwargs)


@dataclass(frozen=True)
class EvidenceSufficiencyV2Verifier:
    version: str = "v2"

    def verify(self, **kwargs) -> EvidenceSufficiencyVerdict:
        return verify_evidence_sufficiency_v2(**kwargs)


def build_evidence_verifier(version: str) -> EvidenceVerifier:
    if version == "v2":
        return EvidenceSufficiencyV2Verifier()
    return EvidenceSufficiencyV1Verifier()
