# Widget Administration Frontend Settings, Domains, and Embed

TASK-067B3 implements the first authenticated widget administration frontend. It uses the B1/B2 backend APIs and does not change public widget runtime behavior.

## Route Structure

Implemented routes:

- `/widgets` - tenant-scoped widget list
- `/widgets/new` - widget creation form
- `/widgets/[widgetId]` - tabbed settings shell

The detail route contains implemented sections only: Overview, Appearance, Conversation, Domains, and Embed. Preview, Publish, Activity, Rollback, and Knowledge selection are intentionally absent until later tasks implement those workflows.

## API Client

`apps/web/lib/api/widgets.ts` provides typed methods for:

- list widgets
- create widget
- get widget detail
- get draft
- update draft
- list/add/remove origins
- rotate public key
- get/update embed metadata
- list supported SDK versions

The shared dashboard API client now supports `POST` and `DELETE` alongside existing `GET` and `PATCH` helpers. Components do not build tenant IDs from user input; they use the current development dashboard session context.

## Widget List

The list displays widget name, publication status, operational status, pilot status, active published revision, and draft dirty state. It does not display the full public key. Empty state explains that widgets can be configured before a later publish workflow makes them public.

## Creation Flow

The create form collects internal display name and environment, seeds safe initial draft defaults, and redirects to the new widget detail route after success. Creation does not publish, pilot-enable, deploy, or rotate keys.

## Settings Shell

The settings shell uses accessible tab buttons for implemented sections. Status presentation keeps Draft, Published, Pilot, Operational, and Release concepts separate.

## Draft Editing

Draft editing uses explicit Save only. Local form state is compared to the last saved draft for dirty detection. Dirty drafts enable Save and Discard controls and install a browser beforeunload warning only while dirty.

Save sends the current `concurrency_version` to the B1 API. A conflict response is not overwritten; the UI shows a conflict state with a reload-latest action.

Save updates only the saved draft. It does not publish and does not change active public configuration.

## Appearance Settings

Supported fields:

- bot name
- launcher label
- primary colour
- secondary colour
- theme mode
- position
- logo URL
- avatar URL

Colour controls combine text input with a native colour swatch. The UI tells admins that runtime colour fallback may adjust colours for accessibility; the backend/runtime remains authoritative.

## Conversation Settings

Supported fields:

- welcome message
- suggested questions
- language
- privacy notice
- privacy URL
- terms URL
- fallback contact text
- citation capability
- conversation-history capability flag

Suggested questions can be added, removed, and reordered with keyboard-accessible buttons. The UI caps editing at six entries and does not truncate silently.

## Domains

The Domains section calls B2 origin APIs. It shows canonical origins returned by the backend, active state, and environment. Add/remove errors surface backend validation, including duplicate origins and final-active-origin protection. Wildcards, paths, queries, and fragments remain backend-rejected.

## Public Key And Rotation

The Embed section displays the current public key and describes it as a public widget key, not a secret. Rotation uses an accessible confirmation dialog and disables duplicate mutation while pending. On success, the UI refreshes embed metadata and shows the new snippet.

## Embed Management

The Embed section renders the backend-generated snippet as text inside a selectable `pre/code` block. It never injects the snippet as HTML. Copy buttons use the Clipboard API and fall back to manual-copy guidance.

Managed major alias is the default. Pinned mode is selected from supported SDK versions returned by the API only. There is no free-text SDK URL, no API origin override, no iframe origin override, and no `latest` option. SRI is displayed only when returned by backend metadata.

## Status And Readiness

Readiness codes from B2 are presented as actionable status text:

- `ready`
- `unpublished`
- `no_allowed_origins`
- `pilot_not_enabled`
- `operationally_disabled`
- `unsupported_sdk_version`

Global kill-switch internals are not exposed.

## Accessibility And Responsive Behavior

The implementation uses semantic headings, labelled inputs, status text, accessible tab buttons, keyboard-friendly suggested-question controls, selectable code blocks, visible focus styles from the existing app, and responsive CSS. On narrow screens, panels collapse to a single column, controls keep usable target sizes, and snippets wrap/scroll without page overflow.

## Tests

`apps/web/components/widgets/widget-admin.test.tsx` covers:

- list rendering without full public key exposure
- create flow and redirect
- draft save with concurrency version
- origin add and metadata refresh
- pinned SDK selection
- inert snippet rendering
- public key rotation confirmation and refresh

## Deferred Work

- Draft iframe preview and preview grants
- Publish workflow UI
- Revision history and rollback UI
- Knowledge-scope selection UI
- Embed installation verification crawler
- Pilot enablement mutation
- Global operational controls

## TASK-067B4 Update

The authenticated administration frontend now includes Knowledge, Preview, Publish, History, and installation-status surfaces. Preview is config-faithful and grant-bound; publish and rollback remain backend-authoritative and do not change pilot or operational controls.
