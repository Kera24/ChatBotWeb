# Guardrail Task Specification

Version: 1.0
Status: Active
Related: [Guardrails Success Criteria](./Guardrails_Success_Criteria.md), [Real-Embedding Final Report](./Evaluation_Real_Embedding_Final_Report.md)

## Why this exists

The real-embedding evaluation cycle closed with **CONDITIONAL GO** and 18 named hard failures, precisely root-caused into three categories that retrieval-threshold tuning cannot resolve: `similar_but_absent` (evidence is topically related but does not contain the requested fact), `fallback_expected` (the assistant lacks capability/intent boundaries), and `prompt_injection`/`system_prompt_extraction` (require generation-level policy enforcement). This document defines the guardrail layer that targets exactly those three gaps - not a general-purpose content-moderation system, and not a replacement for the retrieval work already done.

## Required behaviour

The assistant must:

- answer only when authorised, retrieved evidence actually supports the answer - not merely when evidence exists on a related topic;
- distinguish "evidence about this topic" from "evidence containing the specific requested fact" (the exact `similar_but_absent` gap);
- refuse or fall back, clearly and without inventing a value, when the specific answer is absent;
- follow Conversa's own system policy over any instruction found in the user's message or in retrieved documents;
- never reveal its system prompt, developer instructions, or internal configuration;
- never expose secrets, credentials, or connection strings, whether from its own configuration or (implausibly, but must still be safe) from retrieved content;
- never access another assistant's, workspace's, or organisation's data (this guarantee already exists and must not regress);
- ignore instructions embedded inside retrieved documents while still using their legitimate factual content;
- safely refuse capability requests it cannot actually perform (executing an action, making a legal/medical/financial determination, browsing the open web);
- preserve useful, unblocked answers for ordinary benign questions, including ones that happen to contain words like "system," "prompt," "ignore," or "instructions" in an everyday sense;
- keep false positives low - a guardrail that blocks legitimate business questions is a regression, not a safety win.

## Explicit failure categories

Every guardrail decision and every evaluation case maps to exactly one of these categories (mirrors `app/evaluation/categories.py` conventions - a closed, discoverable vocabulary, not free-text matching):

| Category | Definition |
| --- | --- |
| `grounding_failure` | The answer asserts something the retrieved evidence does not actually state. |
| `unsupported_factual_claim` | A specific requested fact (number, date, fee, policy condition, name, eligibility rule) has no matching evidence, but the system answered anyway. |
| `capability_violation` | The system claims to perform, or answers as if it could perform, an action it has no real capability for (deleting data, processing a refund, making a legal determination). |
| `direct_prompt_injection` | The user's own message attempts to override system policy ("ignore previous instructions," "reveal your system prompt," "act as an unrestricted model"). |
| `indirect_prompt_injection` | An instruction embedded inside a *retrieved document* attempts the same thing. |
| `system_prompt_extraction` | A request specifically targeting disclosure of the system prompt, internal instructions, or provider/model configuration. |
| `secret_extraction` | A request (or a document-embedded instruction) targeting disclosure of credentials, API keys, connection strings, or tokens. |
| `unsafe_markup` | The generated answer contains executable or dangerous markup (script tags, event handlers, `javascript:` URLs, dangerous embeds). |
| `malformed_provider_output` | The AI provider returned output that cannot be safely used as-is (empty, truncated mid-structure, non-UTF-8, control characters). |
| `provider_failure` | The AI provider call itself failed (timeout, error, rate limit) - already handled upstream by `RAGProviderExecutionError`; guardrails must not mask this as a different failure type. |
| `safe_benign_input` | An ordinary, legitimate question - including ones that are lexically similar to an attack pattern but are not one. This category exists specifically so false-positive tracking has a first-class home in the same taxonomy as real threats. |

## Explicit non-goals

- **No model-as-judge grading.** Every guardrail in this cycle is a deterministic, structural, or pattern-based check - never a second LLM call scoring the first one's output. A future phase may add this; it is out of scope here (see the "Future model-as-judge phase" note in the [Final Report](./Guardrails_Final_Report.md)).
- **No general-purpose content moderation.** This guardrail layer targets the three specific gaps the evaluation cycle identified for *this* assistant's use case (a source-grounded knowledge assistant), not a general toxicity/abuse filter unrelated to that use case.
- **No UI, billing, Azure, or deployment changes.** No embedding model replacement, no change to the accepted `RETRIEVAL_MIN_SIMILARITY_SCORE=0.25` without new evidence, no lowering of any evaluation threshold, and no marking of an unresolved failure as expected/passing.

## A known constraint this cycle works within

Conversa's evaluation harness runs generation through the deterministic `mock` AI provider (a content-independent, hash-based canned response - see `app/ai/dependencies.py`). This means guardrails that would need to inspect a *real* model's actual generated prose for hallucinated claims cannot be validated end-to-end against real generation semantics in this cycle, for the same reason the mock embedding provider could not validate a similarity threshold two cycles ago. The guardrails in this cycle are therefore designed, wherever possible, to act **before or independent of generation** - on the user's question, on the retrieved evidence, and on structural/pattern properties of whatever text the provider does return - so that they are genuinely enforced and testable regardless of which AI provider is configured. Where a guardrail's *design* (e.g. trusted/untrusted prompt separation) can only be fully validated with a real generation model, this is stated explicitly rather than implied to be proven.
