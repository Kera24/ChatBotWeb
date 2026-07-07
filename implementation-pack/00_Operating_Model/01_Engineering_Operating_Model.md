# Engineering Operating Model

Version: 1.0
Status: Active Draft

## 1. Project identity

ChatBotWeb / Yoranix AI Platform is a multi-tenant AI knowledge platform for building client-specific RAG chatbots and future AI agents.

This project must be treated as a long-term SaaS product, not a demo chatbot.

## 2. Operating principles

### 2.1 Build from requirements

Every implementation task must map to:

- Product requirement
- System requirement
- Epic
- Task
- Acceptance criteria

### 2.2 Keep MVP boundaries strict

The MVP is not the full platform. It only proves repeatable onboarding, knowledge upload, tenant-aware RAG, website widget deployment, and basic analytics.

### 2.3 Tenant isolation first

Any backend, database, RAG, analytics, or widget code that touches client data must be tenant-aware.

### 2.4 AI output must be grounded

RAG answers must use retrieved context and include citations where possible. If evidence is insufficient, the assistant must use a safe fallback.

### 2.5 Human and AI collaboration

The repository must support both human engineers and AI coding agents. Tasks must include enough context for an agent to implement safely.

## 3. Development lifecycle

```text
Idea
  -> Research
  -> Requirement
  -> Architecture
  -> Epic
  -> Story
  -> Task
  -> Implementation
  -> Review
  -> Test
  -> Merge
  -> Deploy
  -> Monitor
```

## 4. Work item hierarchy

```text
Product Goal
  Epic
    Story
      Task
        Pull Request
          Test Result
```

## 5. Branching model

Recommended branch names:

```text
feature/TASK-002-backend-foundation
feature/TASK-003-frontend-foundation
feature/TASK-004-database-foundation
fix/TASK-XXX-description
```

## 6. Pull request rules

Every PR should include:

- Linked task
- Summary of changes
- Tests run
- Security considerations
- Tenant isolation considerations
- Screenshots for UI changes
- Follow-up tasks

## 7. Definition of ready

A task is ready when it has:

- Objective
- Context links
- Files to create or modify
- Acceptance criteria
- Test expectations
- Constraints
- Definition of done

## 8. Definition of done

A task is done when:

- Acceptance criteria are satisfied
- Tests pass
- No obvious tenant isolation issue exists
- Documentation is updated if behaviour changed
- Code is reviewed
- No secrets are committed

## 9. Quality gates

Before merge, verify:

- Scope matches task
- No unrelated feature work
- No unsafe public endpoint
- No cross-tenant access path
- Errors are handled clearly
- Tests cover critical behaviour
- Dependencies are justified

## 10. Escalation rules

AI coding agents must stop and ask for review when:

- A major dependency is needed
- A security-sensitive design decision appears
- Tenant isolation is unclear
- A task requires changing architecture
- The implementation conflicts with documentation
