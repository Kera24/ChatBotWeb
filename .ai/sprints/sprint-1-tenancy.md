# Sprint 1: Database and Tenancy

Source: `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`

## Goal

Create the database foundation and tenant model.

## In scope

- Database configuration
- Migration setup
- Organisation model
- Workspace model
- User and membership model
- Tenant isolation test patterns

## Out of scope

- Document ingestion
- Embeddings
- Chat runtime
- Widget UI/runtime
- Billing
- Advanced analytics

## Exit criteria

- Initial migration creates core tenant tables.
- Tenant-scoped data access patterns exist.
- Tests prove basic tenant isolation.

## Required checks

- Every tenant-scoped table has appropriate tenant identifiers.
- Queries are designed to filter by organisation and workspace where required.
- Permission model aligns with `docs/06_Security/01_Security_and_RBAC_Model.md`.
- No seed data contains secrets or real client data.
