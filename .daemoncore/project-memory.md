# Project Memory

This file captures long-lived, repo-specific conventions that agents should respect.

## Stable Conventions
- Branch naming:
  - e.g. `feature/<short-name>`, `bugfix/<ticket-id>`.
- Commit style:
  - e.g. Conventional Commits, or custom house rules.
- Code style:
  - e.g. black, isort, eslint config, formatter preferences.

Describe them here so agents can align with the team's habits.

## Domain Concepts
Use this section to explain domain terms that appear throughout the codebase.
- `<TERM>` — definition / usage.
- `<CONCEPT>` — how it maps to modules, APIs, or data structures.

## Testing & Quality
- How to run tests locally.
- What “good enough” looks like for this repo.
- Any required coverage or quality gates.

## Agent Usage Notes
- When to prefer design docs over immediate coding.
- How to structure proposals in `.daemoncore/outbox/`.
- Any repo-specific “do not touch” zones beyond what `project-AGENTS.md` covers.
