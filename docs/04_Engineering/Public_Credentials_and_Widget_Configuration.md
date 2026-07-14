# Public Credentials and Widget Configuration

Status: Implemented admin foundation. No public widget endpoint exists.

## Tables

TASK-057B adds three persistent tables:

- `public_credentials`
- `credential_allowed_origins`
- `widget_configurations`

The migration creates empty tables only. It does not seed credentials and does not make any workspace public.

## Credential Lifecycle

Supported statuses:

- `draft`
- `active`
- `disabled`
- `revoked`
- `expired`

Valid transitions:

- `draft -> active`
- `active -> disabled`
- `disabled -> active`
- `active -> revoked`
- `disabled -> revoked`
- `active -> expired`
- `disabled -> expired`

`revoked` and `expired` are terminal. Deleted credentials cannot activate. Activation requires the workspace to resolve as active within the organisation.

## Identifier Format

Widget public keys use high-entropy URL-safe identifiers:

```text
wpk_dev_<random>
wpk_stg_<random>
wpk_live_<random>
```

The random part is generated with `secrets.token_urlsafe(24)`. Identifiers contain no organisation or workspace information. Collisions are handled by regeneration.

Widget public keys are identifiers, not secrets. Secret-bearing partner/API credentials remain out of scope until a one-time secret return flow is implemented.

## RBAC

Credential and widget configuration management is available only through authenticated development-dashboard APIs.

Allowed:

- `org_owner`
- `client_admin`
- `super_admin` through existing development behaviour

Denied:

- `viewer`
- `contributor`
- non-members

## Admin Endpoints

Credential management:

- `GET /api/v1/workspaces/{workspace_id}/public-credentials?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id=...`
- `PATCH /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/disable?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/revoke?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/rotate?organisation_id=...`

Allowed origins:

- `GET /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins?organisation_id=...`
- `DELETE /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins/{origin_id}?organisation_id=...`

Widget configuration:

- `GET /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config?organisation_id=...`
- `PUT /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config/publish?organisation_id=...`

## Origins

Origins are stored as normalised records with scheme, hostname, optional port, wildcard flag, environment, and active flag.

Validation rejects:

- paths, query strings, fragments, and credentials
- unsupported schemes
- localhost outside development
- non-HTTPS origins outside development
- broad wildcard origins without a concrete hostname
- duplicates for the same credential

Runtime Origin-header validation remains out of scope.

## Widget Configuration

Widget configuration is owned by credential for MVP. A configuration is not created automatically when a credential is created.

The service supports:

- draft create/update through the admin API
- safe text and URL validation
- safe hex colour validation with contrast approximation
- suggested-question count/length limits
- HTML/script rejection
- publish with `configuration_version` increment
- safe public configuration projection for future public config endpoints

## Rotation

Rotation creates a replacement credential with:

- same tenant/workspace
- same credential type
- same environment
- same policy profile
- same capabilities
- shared `rotation_group_id`
- `parent_credential_id` pointing to the old credential

The old credential is not revoked automatically. This supports controlled overlap. Cache invalidation hooks remain future work; audit events are emitted now.

## Audit Events

Implemented events:

- `public_credential.created`
- `public_credential.updated`
- `public_credential.activated`
- `public_credential.disabled`
- `public_credential.revoked`
- `public_credential.rotated`
- `public_credential.expired`
- `public_credential.origin.added`
- `public_credential.origin.removed`
- `widget_configuration.created`
- `widget_configuration.updated`
- `widget_configuration.published`

Audit metadata must not include secrets or secret hashes.

## Safe Response Exclusions

Admin responses never return:

- `secret_hash`
- raw secret-bearing credential values
- internal encryption data
- hidden metadata
- unrelated tenant records

Future public configuration responses must additionally exclude organisation IDs, workspace IDs, credential database IDs, allowed-origin lists, policy internals, provider details, audit metadata, and internal storage paths.

## Public Access Layer Integration

`DatabaseCredentialRegistry` resolves persisted credentials into the existing credential-neutral `CredentialRecord` contract. The in-memory registry remains available for isolated tests.

No public route uses this yet. Future public endpoints must still validate active organisation/workspace, origins, sessions, rate limits, and cost controls before invoking RAG.

## Local Migration and Testing

```bash
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
cd ../..
npm run api:test
npm run verify
```

## Public Endpoint Warning

No public widget config endpoint or public message endpoint exists after TASK-057B. These admin APIs configure future public access only; they do not expose anonymous chat or browser widget runtime behaviour.
