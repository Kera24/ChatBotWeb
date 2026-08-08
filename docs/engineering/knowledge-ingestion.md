# Knowledge Ingestion — Current / Future / Out of Scope

## Current

Document lifecycle upload → extract → chunk → embed → active version, centralized transition rules in `app.services.document_lifecycle` (invalid transitions raise, never silently succeed). Full detail: `docs/architecture/knowledge-ingestion.md`. Decision record: ADR 0026 (manual ingestion before connectors).

## Future

- Connector-based ingestion (Notion/Confluence/Google Drive/website crawl) instead of manual upload only — see `docs/future/ConnectorFramework.md`.
- Continuous/scheduled re-ingestion instead of one-shot upload — see `docs/future/ContinuousIngestion.md`.
- Multimodal documents (images, tables-as-structured-data, audio transcripts) — see `docs/future/MultimodalKnowledge.md`.

## Out of scope (not planned)

- Automatic web-wide crawling/discovery of content not explicitly added by a tenant — ingestion stays pull-based and tenant-initiated even after connectors ship.
