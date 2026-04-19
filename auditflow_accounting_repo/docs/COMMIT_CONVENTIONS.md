# Commit Conventions

## Goal
Keep implementation incremental, reviewable, and aligned with the execution plan.

## Commit format
Use Conventional Commit style:
- `feat:` new functionality
- `fix:` bug fix
- `test:` tests
- `refactor:` code restructuring without behavior change
- `docs:` documentation
- `chore:` configuration/tooling/maintenance

Examples:
- `feat(upload): add document upload endpoint`
- `feat(extraction): structure accounting process from parsed text`
- `feat(rules): add chart-of-accounts inconsistency heuristics`
- `test(pipeline): add integration test for analysis flow`

## Rules
- One commit must represent one reviewable change.
- Do not mix feature work and unrelated refactoring.
- Do not bundle multiple phases into one commit.
- Do not change architecture and feature scope in the same commit.
- Every feature commit should leave the project runnable.

## Agent expectations
Before proposing a commit:
1. confirm the scoped phase was completed
2. confirm relevant tests/checks were run
3. summarize changed files
4. propose one clean commit message

## Recommended sequence style
A typical phase may contain:
- one `feat:` commit for the core functionality
- optionally one `test:` commit if tests are intentionally separated
- optionally one `docs:` commit if documentation changes are material

In most MVP phases, prefer a single `feat:` commit that already includes the relevant tests.
