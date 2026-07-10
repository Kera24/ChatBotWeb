# ADR 0003: Use Immutable, Versioned Prompts

Status: Accepted

## Context

The current prompt assembly foundation uses configured prompt content. As the platform grows, prompt changes will affect answer quality, safety, token use, citation behaviour, and customer experience.

Editing production prompt text in place would make results difficult to reproduce and rollback.

## Decision

Prompts will be stored as logical prompt definitions with immutable versions.

A prompt version can move through lifecycle states such as:

- draft
- testing
- active
- deprecated
- retired

Once activated or used in production, prompt template content cannot be edited in place. Changes require a new version.

Each model execution must record:

- prompt key
- prompt version
- prompt hash

## Alternatives considered

### Hardcode prompts in service modules

Rejected because prompts would be scattered and difficult to audit.

### Store one editable prompt per use case

Rejected because it prevents reproducibility and safe rollback.

## Consequences

### Positive

- Reproducible executions
- Evaluation before activation
- Fast rollback
- Clear audit history
- Future tenant override support

### Negative

- Additional schema and lifecycle complexity
- Prompt activation requires governance
- Cache invalidation must be handled carefully

## Rules

- Platform safety and grounding requirements cannot be weakened by tenant overrides.
- Full prompt text should not be logged by default in production.
- Activation and rollback actions must produce audit events.
