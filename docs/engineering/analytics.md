# Analytics — Current / Future / Out of Scope

## Current

`apps/web/app/analytics/page.tsx` + `apps/web/lib/api/analytics.ts::loadAnalyticsData()` — a **client-side composition** of existing list endpoints (`listConversations`, `listDocuments`, `listWidgets`, `listUnansweredReviewItems`, `getConversationDetail`), not a dedicated backend analytics module or endpoint. Bounded by `RECENT_WINDOW_LIMIT=100` and `DETAIL_SAMPLE_LIMIT=25`. This is distinct from AI Observability (`docs/architecture/observability.md`), which is trace-level and backend-computed; analytics is product/usage-level and frontend-computed today.

## Future

- A dedicated backend analytics aggregation endpoint (removing the `N`-list-calls-plus-client-composition pattern) once usage volume makes client-side composition too slow or too limited — see `docs/roadmap/roadmap.md`.
- Merging cost/quality signals from `ai_model_call_traces` (`docs/architecture/observability.md`) into the analytics view so usage and AI-cost/quality are visible together.

## Out of scope (not planned)

- Cross-tenant/aggregate-across-organisations analytics of any kind — analytics stays scoped to a single organisation's own data, matching tenant isolation.
