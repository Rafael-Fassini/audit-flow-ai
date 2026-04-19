# Codex Phase Prompts

These prompts assume the repository already contains:
- AGENTS.md
- README.md
- docs/ARCHITECTURE.md
- docs/EXECUTION_PLAN.md
- docs/COMMIT_CONVENTIONS.md
- docs/RUNBOOK.md

Use one prompt at a time.

---

## Prompt for Phase 0 — Foundation and toolchain
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 0 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 0
2. list the files you plan to create or modify
3. identify any assumptions or risks

Then:
4. implement only the scoped Phase 0 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- do not implement frontend
- do not change architecture
- do not work on later phases
- keep the code modular and typed
```

## Prompt for Phase 1 — Document ingestion and persistence
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 1 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 1
2. list the files you plan to create or modify
3. identify any assumptions or risks

Then:
4. implement only the scoped Phase 1 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- do not implement parsing yet beyond what Phase 1 requires
- do not implement retrieval or inference
- do not change architecture
- do not implement frontend
```

## Prompt for Phase 2 — Parsing and chunking
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 2 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 2
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around file support

Then:
4. implement only the scoped Phase 2 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- do not implement LLM extraction
- do not implement retrieval or scoring
- do not implement frontend
```

## Prompt for Phase 3 — Domain schemas and process structuring
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 3 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 3
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around schema boundaries and validation

Then:
4. implement only the scoped Phase 3 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- focus on accounting entries and chart of accounts
- do not implement retrieval yet
- do not implement final inference output yet
- do not change architecture
```

## Prompt for Phase 4 — Knowledge base ingestion and retrieval
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 4 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 4
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around vector indexing and retrieval design

Then:
4. implement only the scoped Phase 4 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- keep retrieval simple and robust for MVP
- do not implement the full risk engine yet
- do not add unsupported infra complexity
```

## Prompt for Phase 5 — Inconsistency and risk engine
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 5 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 5
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around rule design and hybrid inference

Then:
4. implement only the scoped Phase 5 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- use a hybrid approach: heuristics + structured data + LLM
- focus on accounting inconsistencies and chart-of-accounts logic
- do not implement frontend
- do not introduce autonomous-agent behavior
```

## Prompt for Phase 6 — Scoring and reporting
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 6 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 6
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around response stability and schema design

Then:
4. implement only the scoped Phase 6 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- produce a stable structured analysis payload
- do not implement export files or dashboards
- do not change architecture
```

## Prompt for Phase 7 — Hardening and documentation
```text
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/EXECUTION_PLAN.md, docs/COMMIT_CONVENTIONS.md, and docs/RUNBOOK.md.

Implement Phase 7 from docs/EXECUTION_PLAN.md.

Before coding:
1. restate the objective of Phase 7
2. list the files you plan to create or modify
3. identify assumptions or risks, especially around logging and operational clarity

Then:
4. implement only the scoped Phase 7 items
5. keep the project runnable
6. add or update the relevant tests
7. run the relevant checks/tests
8. summarize what was completed
9. propose the final commit message for the current checkpoint

Constraints:
- focus on reliability and documentation
- do not introduce new product scope
- keep the MVP lean
```
