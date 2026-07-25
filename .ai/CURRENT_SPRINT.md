# Current Sprint

Current phase:
Sprint 3H — Controlled Production Pilot Deployment

Current task:
TASK-068B4 — Azure Staging Deployment, Live Full-Stack Validation, Monitoring Verification, and Rollback Drill

## Guardrails

- Implement TASK-068B4 staging validation and rollback drill orchestration only.
- Direct B4 execution may target `staging` only; reject `pilot`, `production`, `prod`, and `production-pilot`.
- Do not deploy production-pilot, modify production DNS, enable real customers, use customer data, weaken auth, or log tokens/conversations/drafts/citations.
- Do not claim staging, monitoring, alerting, or rollback is live-verified unless Azure staging execution actually occurs.
- Preserve Azure architecture, immutable artifacts, exact-origin policy, tenant isolation, privacy-preserving telemetry, and controlled approval model.
- Next recommended task after successful staging validation only: TASK-068B5 — Production-Pilot Domain Wiring, Deployment, Synthetic Validation, Manual Accessibility/Security Gate, and First Pilot Enablement.
