---
schema_version: 1
open_count: 4
waived_count: 0
fixed_count: 0
total_count: 4
last_updated: 2026-08-10T10:35:09.782Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 02 | unrun-verify | pyproject.toml |  | ruff format --check fails repo-wide (19 pre-existing Phase 1 files); no [tool.ruff] line-length is configured, so plan 02-01's verification line is unsatisfiable without a repo-wide reformat | open |  | 2026-08-10T08:23:40.701Z |  |
| 2 | 02 | deviation | src/prope/broker/topology.py |  | x-queue-type: classic added beyond the plan's five arguments (Rule 2) — reject-publish-dlx does not exist on a quorum queue, so the Task 1 decision must not rest on a broker default | open |  | 2026-08-10T08:23:42.037Z |  |
| 3 | 02 | stub | src/prope/worker.py |  | ObservedWorkspaces is a Phase 2 stand-in for ADR-0051 access.list_workspaces(); a workspace with no traffic since process start is not swept by the retention job | open |  | 2026-08-10T09:16:56.275Z |  |
| 4 | 02 | deviation | src/prope/session_auth.py |  | assembled_routes() exists because FastAPI 0.141's include_router appends one lazy _IncludedRouter entry — a naive app.routes walk asserts vacuously over an empty set; re-verify on any FastAPI upgrade | open |  | 2026-08-10T10:35:09.782Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "02",
    "file": "pyproject.toml",
    "line": null,
    "description": "ruff format --check fails repo-wide (19 pre-existing Phase 1 files); no [tool.ruff] line-length is configured, so plan 02-01's verification line is unsatisfiable without a repo-wide reformat",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T08:23:40.701Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "02",
    "file": "src/prope/broker/topology.py",
    "line": null,
    "description": "x-queue-type: classic added beyond the plan's five arguments (Rule 2) — reject-publish-dlx does not exist on a quorum queue, so the Task 1 decision must not rest on a broker default",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T08:23:42.037Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "stub",
    "phase": "02",
    "file": "src/prope/worker.py",
    "line": null,
    "description": "ObservedWorkspaces is a Phase 2 stand-in for ADR-0051 access.list_workspaces(); a workspace with no traffic since process start is not swept by the retention job",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T09:16:56.275Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "02",
    "file": "src/prope/session_auth.py",
    "line": null,
    "description": "assembled_routes() exists because FastAPI 0.141's include_router appends one lazy _IncludedRouter entry — a naive app.routes walk asserts vacuously over an empty set; re-verify on any FastAPI upgrade",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T10:35:09.782Z",
    "resolved_at": null
  }
]
````
