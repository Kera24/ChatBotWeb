# TASK-047 � Token Cost Accounting Foundation

Status: Implemented

## Objective

Add provider-neutral usage accounting for AI Core executions without implementing billing, production analytics, database-backed persistence, real provider integrations, chat sessions, or a final RAG endpoint.

## Scope Implemented

- In-memory MVP AI usage accounting repository and service.
- Provider-neutral usage records for AI Core executions.
- Decimal-based estimated cost calculation from model registry pricing metadata.
- Success accounting after provider execution.
- Safe failed and timed-out execution accounting for provider failures and timeout simulations.
- Duplicate execution ID protection in the in-memory repository.
- Internal development endpoint to list recent usage records.
- Super-admin-only access for usage reads through existing temporary development RBAC.

## Recorded Fields

- Execution ID and timestamp.
- Organisation and workspace IDs when supplied.
- Provider key, model key, and provider model name.
- Prompt key, prompt version, and prompt hash.
- Prompt, completion, and total tokens.
- Estimated input, output, and total cost.
- Latency, finish reason, execution outcome, and structured error metadata.

## Out of Scope

- Billing.
- Invoices.
- Tenant pricing plans.
- Production analytics dashboard.
- Database-backed accounting.
- Real provider integrations.
- Chat sessions.
- Final RAG endpoint.

## Verification

Required commands:

- `npm run api:test`
- `npm run verify`
