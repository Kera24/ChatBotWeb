# Epic: Tenant and Workspace Management

## Epic ID

EPIC-002

## Status

Draft

## Problem

The platform must support many client organisations while preventing cross-tenant data access.

## Goal

Implement organisation, workspace, membership, and role foundations so every future feature can safely operate within tenant boundaries.

## Users

- Super admin
- Organisation owner
- Client admin

## Scope

- Organisation model
- Workspace model
- Membership model
- Role model
- Tenant resolution
- Tenant-scoped API patterns

## Out of scope

- Billing
- Full SSO
- Advanced enterprise permissions

## Requirements

- Every organisation has one or more workspaces.
- Every tenant-scoped entity must connect to an organisation or workspace.
- Dashboard users must only access organisations where they have membership.
- Public widget requests must resolve to one active workspace.

## Acceptance criteria

- [ ] Super admin can create an organisation.
- [ ] Workspace can be created inside an organisation.
- [ ] Users can have roles within an organisation.
- [ ] API routes enforce tenant context.
- [ ] Tests prove that Organisation A cannot access Organisation B data.

## Dependencies

- EPIC-001
- docs/02_Architecture/02_Database_Design.md
- docs/06_Security/01_Security_and_RBAC_Model.md

## Risks

- Tenant isolation bugs
- Role model becoming too complex too early

## Implementation notes

Start with a simple role model and expand only when pilot customers need it.
