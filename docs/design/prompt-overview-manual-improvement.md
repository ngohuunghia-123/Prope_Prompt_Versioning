# Prompt overview and manual PropAI improvement

## Understanding

- Prompt authors need to inspect versions, declare intended usage, and request an improvement analysis without surrendering control of revision creation.
- The usage survey belongs in **Monitor & improve**, where it supplies context for analysis, rather than in the editor.
- A manual PropAI run analyses the selected revision and, when present, production evidence from the live revision.
- The agent may open a finding or a gated proposal. It never creates, approves, or releases a revision.
- Prompt overview addresses use the immutable registry model name: `/app/prompts/{namespace}/{name}`.
- Existing ID-based write routes remain internal implementation addresses.

## Assumptions and non-functional requirements

- Only one explicit improvement run per prompt and requesting user may be active at once.
- Run creation is idempotent and reload-safe; periodic analysis remains independent.
- Permission-filtered reads preserve the existing not-found behaviour for invisible prompts.
- The sidebar exposes operational progress and evidence references, never model chain-of-thought.
- If no live revision exists, selected-revision analysis is allowed but the UI explicitly states that production evidence is unavailable.
- Provider cost cannot be estimated reliably, so confirmation describes possible cost without inventing a number.

## Decision log

1. **Usage wizard location:** Monitor & improve, one auto-saved axis per step. The readiness findings remain in edit mode.
2. **Analysis scope:** selected revision plus live revision; selected-only when the prompt is not live.
3. **Cost control:** explicit confirmation before creating a run.
4. **Trust surface:** an inline evidence-trail card in the version sidebar; the version list remains available.
5. **Human control:** accepting a proposal opens a candidate in the editor; saving there is the only revision-creating act.
6. **Canonical address:** immutable `namespace/name`, with ID overview URLs redirected using `replace` while preserving search parameters.

## Design

The version rail keeps its two primary actions. Confirming **Suggest edits with PropAI** creates or reconnects to an improvement run. A compact evidence trail appears below the actions and communicates the captured scope, current operational step, limitations, and final review action. The memorable element is the vertical evidence trail: progress is represented as a sequence only because the backend plan is genuinely ordered. Everything else uses the existing Prope surface, ink, muted, border, focus, warning, and primary tokens.

The usage wizard appears near the start of Monitor & improve. It asks one of the four existing usage-profile questions at a time, writes through the current declaration endpoint, and advances only after a successful response. A completed declaration collapses to a summary with an edit action.

The content overview places the fallback answer in the leading metadata block. Template-variable chips live inside their parameter cell. The redundant evaluation-result cell and trailing fallback section are removed.

The backend resolves model-name URLs with the same permission check as ID reads. Improvement agent runs snapshot selected/live references, execute production detection and selected-revision review, gate any candidate against an available suite, and finish with structured review actions. No path in the executor writes a registry revision.

