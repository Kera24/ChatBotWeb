# Services

This folder contains backend services that may run separately as the platform grows.

## Planned services

- `ingestion-service` - extracts and chunks knowledge sources
- `rag-service` - performs retrieval and answer generation
- `agent-service` - future tool-using agent orchestration
- `evaluation-service` - evaluates retrieval and answer quality

For the MVP, some services may begin as modules inside `apps/api` before being separated.
