# Durable prompt ingestion and authoring agent

## Understanding summary

- Prope needs single and bulk prompt import without weakening immutable revisions, tenant isolation, or human confirmation.
- V1 accepts TXT, Markdown, JSON, YAML, CSV, XLSX, and ZIP, with either one prompt per file or one prompt per mapped row/record.
- A dedicated batch workspace owns review; chat starts, resumes, explains, and prepares actions against the same durable resources.
- The authoring agent may search/read, inspect versions and diffs, import, propose metadata changes, and propose fixes as new revisions.
- Reads run automatically. Registry writes require a versioned proposal and explicit confirmation. Approval, release, and evaluation are out of scope.
- V1 supports 100 prompts per batch, targets a review-ready preview within five minutes, and retains uncommitted staging for seven days.
- Success is at least 90% completion on the authoring task suite and zero unauthorized writes.

## Assumptions

- Existing registry commands, canonical XML validation, access control, property history, conversion, and search remain authoritative.
- Exact prompt ID or namespace/name can select a revision target; semantic similarity is advisory only.
- No object store is introduced. Bounded uploads are parsed at admission and extracted staging content is stored under workspace RLS.
- Source and canonical bodies never enter logs, metrics, traces, action previews, or worker scheduling arguments.
- The repository's single RabbitMQ work-queue invariant remains intact; ingestion uses the evaluation module's PostgreSQL claim-loop pattern.

## Decision log

| Decision | Alternatives | Reason |
| --- | --- | --- |
| Explicit `files` and `table` modes | Agent guesses document structure | Deterministic, explainable parsing and retry behavior |
| Durable batch/item resources | Chat-carried conversion output | Artifacts survive turns, crashes, and confirmation requests |
| PostgreSQL claim loop | Second RabbitMQ work queue | Preserves the repository's enforced single-queue topology |
| Dedicated review workspace | Chat cards or repeated single import form | A table is the safe review surface for up to 100 candidates |
| Tiered confirmation | Autonomous drafts or one confirmation per item | Efficient bulk work without delegating immutable writes |
| Exact identity automation only | Semantic auto-merge | Protects prompt identity and revision history |
| Typed governed capability catalogue | Dynamic discovery or direct REST access | Keeps schemas, permissions, risk, executors, and tests together |
| Per-item commits | Whole-batch transaction | Short transactions, resumability, and explicit partial success |

## Architecture

`prompt_ingestion` owns admission, deterministic parsers, batch/item persistence,
AI processing, review versions, commit proposals, retries, and expiry. PostgreSQL
is the source of truth. Workers claim one item with a lease, checkpoint conversion
and duplicate analysis independently, and can safely reclaim interrupted work.

The chat orchestrator receives resource identifiers rather than source bodies.
Model-selected capabilities are filtered through a typed catalogue. Read and
prepare capabilities execute directly; write capabilities create a proposal
whose confirmation rechecks permissions and resource versions before dispatching
to an allow-listed domain handler.

The frontend uploads directly to ingestion, renders a paginated review table,
allows metadata and create/revise/skip decisions, previews canonical XML or a
revision diff, retries failed rows, and confirms a selected snapshot.

## Safety and operations

- RLS and workspace transactions apply to every ingestion record.
- ZIP traversal, symlinks, encrypted/nested archives, macros, formulas, excessive
  expansion, count overflow, and unsupported formats are refused before staging.
- Imported text is data, never a routing instruction. AI stages return typed
  outputs and cannot add workflow steps.
- Transient AI/database failures retry three times with backoff; terminal and
  validation failures are item-local.
- Content-free metrics cover stage latency, state counts, retries, conflicts,
  oldest work age, and purge lag.
- Uncommitted staging is purged seven days after completion or abandonment.

## Acceptance

The release must process a 100-item mixed-format reference batch to review-ready
within five minutes, safely handle partial provider failure, commit selected
create/revise rows exactly once, reject stale proposals, preserve provenance and
history, and pass the backend suite plus frontend typecheck, lint, and build.
