from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from app.access.messages.abuse.contracts import AbusePolicy, AbuseReasonCode

RuleResult = tuple[AbuseReasonCode | None, str | None]
RuleFunction = Callable[[str, AbusePolicy, tuple[str, ...], str], RuleResult]

_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_BASE64ISH_RE = re.compile(r"[A-Za-z0-9+/=_-]{180,}")
_SYSTEM_PROMPT_RE = re.compile(r"\b(system prompt|developer message|hidden instructions|initial instructions|show (me )?your instructions|reveal (the )?prompt)\b", re.IGNORECASE)
_INSTRUCTION_OVERRIDE_RE = re.compile(r"\b(ignore|disregard|forget) (all |any |the )?(previous|prior|above|earlier) instructions\b|\bjailbreak\b|\bact as developer mode\b", re.IGNORECASE)
_CROSS_TENANT_RE = re.compile(r"\b(other|another) (tenant|customer|workspace|organisation|organization|company|client)['’]?s? (private|confidential|secret|data|documents|messages)\b|\bcross[- ]tenant\b", re.IGNORECASE)
_AUTOMATION_RE = re.compile(r"\b(load test|benchmark flood|bot traffic|automated scraping|scrape all|crawl all)\b", re.IGNORECASE)
_STRUCTURED_PAYLOAD_RE = re.compile(r"^\s*(\{\s*\"(role|messages|tools|system|function_call)\"|\[\s*\{\s*\"role\")", re.IGNORECASE | re.DOTALL)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class AbuseRule:
    key: str
    version: str
    evaluate: RuleFunction

    @property
    def stable_id(self) -> str:
        return f"{self.key}:{self.version}"


def _excessive_repeated_characters(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    threshold = max(8, policy.repeated_character_threshold)
    if re.search(rf"(.)\1{{{threshold},}}", message):
        return "excessive_repetition", "repeated_characters"
    return None, None


def _excessive_repeated_phrases(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    words = re.findall(r"[\w'’]+", message.lower())
    if len(words) < 8:
        return None, None
    threshold = max(4, policy.repeated_phrase_threshold)
    for size in (1, 2, 3):
        counts: dict[tuple[str, ...], int] = {}
        for idx in range(0, len(words) - size + 1):
            phrase = tuple(words[idx : idx + size])
            counts[phrase] = counts.get(phrase, 0) + 1
            if counts[phrase] >= threshold:
                return "excessive_repetition", "repeated_phrase"
    return None, None


def _excessive_urls(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    urls = _URL_RE.findall(message)
    if len(urls) > policy.max_urls_per_message:
        return "excessive_urls", "url_count"
    for url in urls:
        if len(url) > policy.max_url_length:
            return "excessive_urls", "url_length"
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "unsupported_payload", "url_shape"
    return None, None


def _encoded_payload(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    for candidate in re.findall(r"[A-Za-z0-9+/=_-]{180,}", message):
        encoded_chars = sum(1 for char in candidate if char.isalnum() or char in "+/=_-")
        ratio = encoded_chars / max(1, len(candidate))
        if ratio >= policy.encoded_payload_ratio_threshold and _BASE64ISH_RE.fullmatch(candidate):
            return "encoded_payload", "encoded_payload"
    return None, None


def _unsafe_control_pattern(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _CONTROL_RE.search(message):
        return "unsafe_control_pattern", "control_pattern"
    return None, None


def _system_prompt_extraction(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _SYSTEM_PROMPT_RE.search(message):
        return "system_prompt_extraction", "system_prompt_pattern"
    return None, None


def _instruction_override(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _INSTRUCTION_OVERRIDE_RE.search(message):
        return "instruction_override", "instruction_override_pattern"
    return None, None


def _cross_tenant_probe(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _CROSS_TENANT_RE.search(message):
        return "cross_tenant_probe", "cross_tenant_pattern"
    return None, None


def _suspicious_automation(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _AUTOMATION_RE.search(message):
        return "suspicious_automation", "automation_pattern"
    return None, None


def _unsupported_payload(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    if _STRUCTURED_PAYLOAD_RE.search(message):
        return "unsupported_payload", "structured_payload"
    return None, None


def _repeated_message(message: str, policy: AbusePolicy, recent: tuple[str, ...], message_hash: str) -> RuleResult:
    repeat_count = sum(1 for fingerprint in recent if fingerprint == message_hash)
    if repeat_count >= policy.repeated_message_limit:
        return "repeated_message", "session_repeat"
    return None, None


DEFAULT_ABUSE_RULES: tuple[AbuseRule, ...] = (
    AbuseRule("unsafe_control_pattern", "v1", _unsafe_control_pattern),
    AbuseRule("repeated_characters", "v1", _excessive_repeated_characters),
    AbuseRule("repeated_phrases", "v1", _excessive_repeated_phrases),
    AbuseRule("excessive_urls", "v1", _excessive_urls),
    AbuseRule("encoded_payload", "v1", _encoded_payload),
    AbuseRule("system_prompt_extraction", "v1", _system_prompt_extraction),
    AbuseRule("instruction_override", "v1", _instruction_override),
    AbuseRule("cross_tenant_probe", "v1", _cross_tenant_probe),
    AbuseRule("suspicious_automation", "v1", _suspicious_automation),
    AbuseRule("unsupported_payload", "v1", _unsupported_payload),
    AbuseRule("repeated_message", "v1", _repeated_message),
)
