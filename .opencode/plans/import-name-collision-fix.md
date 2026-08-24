# Import name collisions: unique proposals, honest errors, editable card

## Diagnosis (2026-08-24 session)
- Import turn succeeded; card staged with default identity `imported/prompt-da-nhap`
- Duyệt → `409 registry_model_name_taken` ×3 — the name from an earlier import
  still exists and model names are immutable (A-021); the card was unapprovable
- FE mapped the 409 to the generic `chat_agent_unavailable` ("Chưa thể trả lời…")

## F1 — Uniquify import proposals before staging (`orchestrator.py`, `tools.py`)
- Replace the `CREATE_PROMPT` lambda (orchestrator.py:563) with `_step_create_prompt`:
  - builds via `propose_create_prompt(title=d.query or "Prompt đã nhập")`
  - then loops `load_prompt_by_model_name(namespace, slug)`: suffix `-2`, `-3`…
    (≤9 attempts) for both slug and display title ("Prompt đã nhập 2")
  - updates proposal arguments/preview/summary so card == what will run
- Pure builder stays pure; the db check lives in the step (inside the transaction)

## F2 — Honest decide errors (`ChatProvider.tsx`, locales en/vi)
- In `decide()`'s catch: when `isApiError(cause)?.code === 'registry_model_name_taken'`
  set a distinct error rendered as new key `chat.refusal.chat_action_name_taken`
  - vi: "Tên prompt đã tồn tại. Đổi tên trên thẻ rồi duyệt lại, hoặc từ chối và thử lại."
  - en: "That prompt name is already taken. Rename it on the card and approve again, or reject."
- Keep `chat_agent_unavailable` only as the last-resort fallback

## F3 — Editable name/title on create_prompt cards
Backend:
- `ActionDecisionCreate` gains optional `edits: dict[str, str] | None`
  (`extra="forbid"` stays)
- Whitelist per tool in orchestrator: `create_prompt → {title, name}`;
  every other tool rejects edits (400) — never body/access_level/namespace
- Server normalises: title trimmed ≤200; name re-slugged via the same
  `tools.slugify`; re-run the F1 uniqueness loop on the edited name
- The settle transaction persists the patched `arguments` **and** `preview`
  before `confirm_action`, preserving "approved == what runs"; log the edit
Frontend:
- `decideChatAction(actionId, approve, edits?)` sends the patch
- `ChatApprovalCard`: for `create_prompt`, Title + Name render as inputs
  prefilled from preview; other tools unchanged read-only
- Small helper label key `chat.pending.editableHint`

## Tests
- Unit: uniquify loop; edits whitelist (unknown tool/field rejected); slug
  normalisation of edited names; uniqueness re-checked after edit
- Integration (test_chat_api): decide with edits executes patched arguments;
  decide without edits unchanged
- FE: tsc + lint (+ build left to user per their preference)

## Notes
- No migration (JSONB columns already hold arguments/preview)
- With F1+F3 the 409 becomes practically unreachable; F2 keeps it honest if it happens
