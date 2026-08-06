"""Layers A (grounding verification) and B (similar-but-absent handling): a
deterministic, pre-generation check on whether the *retrieved evidence*
actually supports the *specific* fact the question asks for - not just
whether it is topically related.

This is intentionally not a claim of perfect hallucination detection (see
docs/04_Engineering/Guardrails_Task_Specification.md). It is one signal,
combined with the retrieval-similarity threshold already enforced upstream
(RETRIEVAL_MIN_SIMILARITY_SCORE) and with citation enforcement
(app.ai.guardrails.citation_policy) - never the sole check a real answer's
correctness rests on.

Method: extract "distinctive terms" from the question (capitalised
non-sentence-initial words - a proper-noun/tier-name heuristic - plus a small,
explicit root-form vocabulary of time-period qualifiers). If the question has
no distinctive terms, there is nothing specific to verify and grounding
passes trivially (this avoids false positives on ordinary questions with no
narrow qualifier). If it does, grounding passes when at least one retrieved
chunk's content-or-title contains *every* distinctive term as a substring
(case-insensitive, root-form matching so "annual"/"Annual"/"annually" and
"month"/"monthly" are treated as the same signal) - i.e. some single piece of
evidence plausibly speaks to the exact combination requested, not just the
general topic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.guardrails.reason_codes import GuardrailReasonCode

SAFE_MESSAGE_FACT_NOT_SUPPORTED = (
    "The available knowledge base doesn't contain that specific detail. "
    "I found related information, but not the exact fact you asked about."
)

# Root forms only (not "monthly"/"annually") so substring matching naturally
# covers every inflection - "month" matches "month", "monthly", and "per
# month" alike, without needing a separate entry per word form.
_QUALIFIER_ROOTS: tuple[str, ...] = ("annual", "month", "quarter", "week", "two-year", "one-year", "three-year", "biennial")

# Common pronouns, contractions, and question/sentence-starter words are
# never treated as distinctive terms, however they are capitalised or
# positioned - English capitalises "I" everywhere, and a malformed/adversarial
# input (e.g. HTML injected before the real question) can push the genuine
# first word of a question past index 0, where it would otherwise look like a
# proper noun.
_EXCLUDED_TERMS = frozenset({
    "i", "i'm", "i've", "i'll", "i'd", "im", "ive",
    "how", "what", "when", "where", "why", "who", "which", "whom",
    "can", "could", "would", "should", "will", "shall", "may", "might",
    "please", "tell", "is", "are", "do", "does", "did", "am", "was", "were",
})

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


@dataclass(frozen=True)
class GroundingVerdict:
    passed: bool
    reason_code: GuardrailReasonCode
    distinctive_terms: tuple[str, ...] = ()
    safe_message: str | None = None


def extract_distinctive_terms(question: str) -> tuple[str, ...]:
    terms: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(question.strip()) or [question]:
        words = _WORD.findall(sentence)
        for index, word in enumerate(words):
            if index == 0:
                continue  # skip the sentence-initial word - capitalisation there is just English grammar, not a proper noun signal
            if word.lower().replace("'", "") in _EXCLUDED_TERMS:
                continue
            if len(word) >= 3 and word[0].isupper() and not word.isupper():
                # Strip a trailing possessive ("Northwind's" -> "Northwind") so the
                # term still matches evidence content that mentions the same proper
                # noun without the possessive suffix.
                normalised = re.sub(r"'s$", "", word)
                terms.add(normalised if len(normalised) >= 3 else word)
    lowered = question.lower()
    for root in _QUALIFIER_ROOTS:
        if root in lowered:
            terms.add(root)
    return tuple(sorted(terms))


_MAX_TERMS_TO_CHECK = 3  # a long/chatty question can accumulate several incidental capitalised words or filler-derived qualifiers unrelated to the actual fact requested; beyond this many terms the signal is too noisy to trust (see docs/04_Engineering/Guardrails_Task_Specification.md's honesty note on this being a heuristic, not perfect hallucination detection) - fall through to grounding_passed rather than risk a false block on a legitimately answerable question.


def verify_grounding(*, question: str, chunk_contents: list[str], chunk_titles: list[str] | None = None) -> GroundingVerdict:
    distinctive_terms = extract_distinctive_terms(question)
    if not distinctive_terms or len(distinctive_terms) > _MAX_TERMS_TO_CHECK:
        return GroundingVerdict(passed=True, reason_code=GuardrailReasonCode.GROUNDING_PASSED)

    titles = chunk_titles or [""] * len(chunk_contents)
    for content, title in zip(chunk_contents, titles):
        searchable = f"{content} {title}".lower()
        if all(term.lower() in searchable for term in distinctive_terms):
            return GroundingVerdict(passed=True, reason_code=GuardrailReasonCode.GROUNDING_PASSED, distinctive_terms=distinctive_terms)

    return GroundingVerdict(
        passed=False,
        reason_code=GuardrailReasonCode.REQUESTED_FACT_NOT_SUPPORTED,
        distinctive_terms=distinctive_terms,
        safe_message=SAFE_MESSAGE_FACT_NOT_SUPPORTED,
    )
