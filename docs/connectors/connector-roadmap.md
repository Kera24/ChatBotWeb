# Supported Connector Roadmap

Every connector type under consideration, its category, and its priority category per `docs/priorities/priority-matrix.md`. None are built today (`docs/adr/0026-manual-ingestion-before-connectors.md`) — this table exists so a future connector's priority is a lookup, not a re-litigated debate, and so demand evidence can be tracked per-connector over time.

| Connector | Category | Typical auth model | Notes |
|---|---|---|---|
| Microsoft 365 (general) | Productivity suite | OAuth2 (Microsoft identity platform) | Umbrella entry; SharePoint/OneDrive below are its concrete surfaces. |
| SharePoint | Productivity suite | OAuth2, delegated site scope | Site-scoped permission, never tenant-wide Graph access by default. |
| OneDrive | Productivity suite | OAuth2, delegated | Personal/business OneDrive; same auth family as SharePoint. |
| Google Workspace (general) | Productivity suite | OAuth2 (Google identity) | Umbrella entry; Google Drive below is its concrete surface. |
| Google Drive | Productivity suite | OAuth2, delegated, folder/drive scope | Folder-scoped permission preferred over full-drive access. |
| Notion | Knowledge base | OAuth2 (Notion integration token) | Page/database-scoped via Notion's own integration-sharing model. |
| Confluence | Knowledge base | OAuth2 / API token | Space-scoped access preferred. |
| Slack | Messaging/collaboration | OAuth2 (Slack app) | Channel-scoped; highest sensitivity around what counts as "knowledge" vs. ephemeral chat — needs explicit tenant curation, not full-history ingestion by default. |
| Teams | Messaging/collaboration | OAuth2 (Microsoft identity platform) | Same sensitivity considerations as Slack. |
| Dropbox | File storage | OAuth2 | Folder-scoped. |
| GitHub | Developer/docs | OAuth2 / installation token | Repo-scoped (e.g. a docs/ directory or wiki), not full-org access. |
| REST APIs (generic) | Custom/programmatic | API key / OAuth2, per-source | Requires a per-integration adapter — "generic REST connector" is a framework capability, not a single connector. |
| Databases | Structured data | Connection credentials | Highest-risk category — read-only credentials mandatory, query scope explicitly bounded, never a live query-time connection substituting for ingestion. |
| Email | Communication | OAuth2 (IMAP/Graph/Gmail API) | Highest sensitivity/privacy profile of any source type — requires the most conservative default scope and explicit tenant opt-in per mailbox. |
| CRM systems | Business data | OAuth2 / API key, per-vendor | Vendor-specific (Salesforce, HubSpot, etc.); each is effectively its own connector despite the shared "CRM" label. |

## Prioritization

See `docs/priorities/priority-matrix.md` for where each connector currently sits. As a starting heuristic (subject to real demand evidence, not fixed): productivity-suite and knowledge-base connectors (SharePoint, OneDrive, Google Drive, Notion, Confluence) are the most likely first-built category given they map most directly onto "documents a tenant already has," while messaging (Slack/Teams), databases, email, and CRM connectors carry higher sensitivity/complexity and are expected later, gated more strictly on confirmed demand.

## Adding a connector to this list

A connector type must appear here (with category, auth model, and any source-specific sensitivity notes) before implementation begins, per `docs/connectors/connector-framework.md`'s onboarding standards.
