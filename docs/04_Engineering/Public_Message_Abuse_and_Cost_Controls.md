# Public Message Abuse And Cost Controls

TASK-063B2 adds an internal security-preparation layer for future public widget messages. It does not expose `POST /api/v1/widget/{public_key}/messages` and does not call retrieval, RAG, AI Core, providers, external moderation, or billing systems.

## Deterministic Abuse Scope

The MVP abuse layer is rule-based and conservative. It is intended to reject or restrict obvious unsafe or abusive inputs before expensive processing, not to solve prompt injection deterministically.

Rules cover:

- excessive identical-character repetition
- excessive repeated words or short phrases
- excessive URL count or URL length
- long contiguous encoded/base64-like payloads
- unsafe control characters
- obvious system-prompt extraction requests
- obvious instruction-override requests
- cross-tenant private-data probing
- unsupported structured prompt/tool payloads
- repeated identical request fingerprints within a session

Rule outputs include stable rule keys, versions, reason codes, and safe counts only. Raw messages, URLs, idempotency keys, session tokens, public keys, and Origins are not emitted.

## False-Positive Philosophy

Weak signals use `allow_with_restrictions` where practical. Strong explicit signals such as system-prompt extraction, instruction override, cross-tenant probing, encoded payloads, unsafe controls, and unsupported structured payloads reject with the generic public-safe `unsafe_request` code.

Session blocking is supported only for explicit `block_session` decisions. The default rules do not block a session on a single weak heuristic.

## Restrictions

`allow_with_restrictions` produces the `conservative_public_answer` restriction profile. The security layer applies restricted ceilings before future RAG execution:

- lower retrieval limit
- lower maximum context characters
- lower maximum output tokens

Future output sanitisation and RAG adapter tasks may also use this profile to disable links, force stricter fallback behaviour, or tighten citation handling.

## Token Estimation

Token estimation is local and deterministic. It uses the larger of:

- a rough word/punctuation piece count
- UTF-8 byte length divided by four, rounded up

This intentionally avoids provider calls and external tokenizer dependencies. Estimates are approximate and biased for pre-execution cost protection, not billing accuracy.

## Model And Pricing Resolution

Cost control resolves the server-selected model through the existing AI `ModelRegistry`, requires the model to be enabled, and confirms it is allowed by the public policy. Pricing uses the model's Decimal input/output cost-per-million-token fields.

The default local mock model has zero cost, which keeps local tests deterministic.

## Cost Ceilings

The cost policy derives server-owned limits from the Public Access policy profile plus safe defaults:

- maximum message tokens
- retrieval limit
- maximum context characters
- estimated context tokens
- maximum output tokens
- provider timeout
- allowed model keys
- session message cap
- optional daily workspace message/token/cost quotas

Public clients cannot override model, provider, prompt, retrieval, context, output, timeout, token, or quota values.

## Usage And Quota Boundary

TASK-063B2 defines a `PublicUsageRepository` abstraction and a deterministic in-memory implementation for tests. Daily workspace message, token, and estimated-cost quotas are optional and disabled by default. No persistent quota table or billing plan is added.

## Failure Behaviour

- Abuse reject: mark the idempotency record `failed`, keep the TASK-063B1 consumed message slot, emit safe events, and stop before RAG.
- Cost/quota reject: mark the idempotency record `failed`, keep the consumed slot, emit safe events, and stop before RAG.
- Explicit block decision: mark the public session blocked through `PublicSessionService`, mark idempotency failed, and stop before RAG.
- Model/policy dependency failure: return a safe unavailable-style decision without exposing model/provider details.

A duplicate retry with the same idempotency key sees the failed idempotency state from TASK-063B1 and does not consume another slot.

## Safe Errors And Events

Public-safe errors remain generic:

- abuse rejection -> `unsafe_request`
- quota/budget rejection -> `quota_exceeded`
- model/policy unavailable -> `temporarily_unavailable`
- unexpected failure -> `safe_internal_error`

Events added:

- `widget.message.abuse_check_started`
- `widget.message.abuse_allowed`
- `widget.message.abuse_restricted`
- `widget.message.abuse_rejected`
- `widget.message.session_blocked`
- `widget.message.cost_check_started`
- `widget.message.cost_allowed`
- `widget.message.quota_denied`
- `widget.message.cost_policy_invalid`
- `widget.message.security_preparation_completed`
- `widget.message.security_preparation_failed`

Events carry request/trace/channel/credential/outcome/error code only through the current in-memory sink shape.

## Local Tests

```powershell
cd apps/api
python -m pytest tests/test_public_message_security.py
python -m pytest tests/test_public_message_preparation.py tests/test_public_sessions.py tests/test_public_widget_session_endpoint.py tests/test_public_widget_configuration_endpoint.py tests/test_public_access_layer.py
```

Full verification:

```powershell
npm run api:install
npm run api:test
npm run verify
git diff --check
```
