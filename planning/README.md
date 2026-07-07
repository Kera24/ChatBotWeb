# AI-Native Planning Workspace

This folder contains structured planning assets for AI-assisted development.

The goal is to make the repository understandable to human engineers and coding agents such as Codex, Cursor, Claude Code, or other multi-agent development tools.

## Structure

- `epics/` - large product capabilities
- `stories/` - user stories linked to epics
- `tasks/` - implementation-ready engineering tasks
- `agents/` - role definitions for specialised AI agents
- `prompts/` - reusable prompts for implementation, review, testing, and refactoring
- `templates/` - standard formats for epics, stories, tasks, and agent briefs

## Rule

No major feature should be implemented until it has:

1. An epic or story reference
2. Acceptance criteria
3. A task breakdown
4. Clear files or modules to touch
5. Testing expectations
6. A definition of done
