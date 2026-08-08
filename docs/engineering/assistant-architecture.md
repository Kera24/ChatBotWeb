# Assistant Architecture — Current / Future / Out of Scope

## Current

An "assistant" is modeled as a `Widget` entity (`apps/api/app/db/models/public_access.py`), scoped to a workspace, with:

- **Configuration as immutable revisions** (`WidgetConfigurationRevision`): a revision is `draft` or `published`. `publish_widget()` clones the current draft into a new `published` revision, then immediately clones a fresh draft off it — editing always continues on a draft while the last published revision stays immutable and servable. See ADRs 0016 (deployment/versioning/release model) and 0017 (publishing/embed management model) for the full reasoning.
- **Knowledge scope**: `knowledge_scope_json` (a list of document IDs) on the configuration — the assistant only ever retrieves from documents in its own scope; an empty scope retrieves zero chunks, never "everything" (see `docs/architecture/retrieval.md`'s knowledge-scoping section — this is a tenant/scope-isolation-adjacent invariant, not a convenience default).
- **Public delivery**: one `PublicCredential` per widget (public key), origin allowlist (`CredentialAllowedOrigin`), embed version pinning (`managed_major` vs `pinned`), served through the widget iframe + SDK (ADRs 0014/0015) and the public access gateway (ADRs 0005-0013).
- **One core, one channel**: every assistant, regardless of how it's invoked (dashboard test or public widget), runs through the exact same `RAGOrchestrator` (`docs/architecture/retrieval.md`) — no per-assistant forked logic.

## Future

- A second channel type (Slack/Teams/voice) as a new `app.access.channels.*` adapter, with the assistant concept remaining channel-independent — see `docs/CONSTITUTION.md`'s long-term platform vision and `docs/future/AgentFramework.md`.
- Per-assistant model/provider routing once more than one live provider exists (`docs/future/ModelRouting.md`).
- Per-assistant evaluation datasets tied 1:1 to a specific assistant's knowledge scope (partially already true via `EvaluationDataset.widget_id` — see `docs/architecture/evaluation.md`).

## Out of scope (not planned)

- Assistants owned by more than one workspace ("shared" assistants across tenants) — would break the tenant-isolation invariant and is not planned.
- Assistant-to-assistant delegation/composition (one assistant calling another) — no current design, not scheduled; would fall under `docs/future/AgentFramework.md` if ever pursued.
