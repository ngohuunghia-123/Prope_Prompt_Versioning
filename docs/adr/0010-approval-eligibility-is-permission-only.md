# ADR-0010 — Approval eligibility is a permission question only; self-approval is recorded, not blocked

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: user
**Module**: release-control, access-control (written while locking release-control)
**Related**: A-007, A-008, A-009, A-075, ADR-0005, ADR-0007, OQ-006, BR-04, NFR-01
**Supersedes**: the agent-decided form of A-008 ("the reviewer of a revision must not be its author")

## Context

While locking release-control, the author-is-not-reviewer rule (A-008, agent-decided) was written into
the module as a server-side refusal with its own counter, acceptance criterion, and security test.

The user overturned it: *anyone should be able to review or approve if they are given the correct
permission; the creator is not permanently barred.*

The original rationale cited `BRIEF.md` §9.2, which argues HITL as internal control in these terms:
*"người viết một thay đổi lên production không nên là người **duy nhất** phát hành nó"* — the person who
writes a change to production should not be the **only** person who releases it. That sentence argues
for the existence of a control. It does not argue for an author-based exclusion, and the agent-decided
assumption over-read it.

## Decision

**Who may approve is answered by access-control and nothing else.** Any actor holding the approve
permission on a prompt may approve any revision of it, including one they authored. No person-level
segregation rule exists anywhere in the system: not author-vs-approver, not approver-vs-releaser
(A-075).

**Self-approval is recorded.** When the approver is the revision's author, the `approval` row stores
`self_approved = true`, the `revision_approved` history event *(renamed from `approved` by A-120; corrected 2026-08-09, step 6 pass 1)* carries it, and
`prope_release_self_approval_total` counts it. A workspace can therefore see how often it happens
without the system having an opinion about whether it should.

A workspace that wants author-approver separation expresses it by not granting approve to authors —
the same control, located in the module that owns the question (OQ-006, A-007).

## Alternatives rejected

**Keep the hard refusal** (the previous A-008). Rejected by the user, and the mechanics support the
call. In a team small enough to have one eligible reviewer, the refusal makes break-glass (A-009) the
only route forward — trading a documented approval carrying a reason for a release with **no approval
record at all**. That is strictly worse than the thing the rule was preventing, and it is the same
failure ADR-0005 rejected a hard block to avoid. A control whose escape hatch is worse than its failure
mode is not a control.

**Make it configurable per workspace** — a policy toggle for "require a different approver". Rejected
for the MVP: a configurable policy engine is explicitly out of scope
(`00_context.md#scope`), and this would be its first rule, arriving without the surface that manages
it. The permission grant already expresses the same intent, so the toggle would be a second place to
say one thing.

**Warn on the review screen without recording it** — a banner reading "you authored this revision".
Rejected as insufficient rather than wrong: a banner shapes one decision and leaves no trace. The
question worth answering later is *how often does this happen and to which prompts*, and only a stored
field answers that. The banner ships too — it is just not the mechanism.

## Consequences

- Release-control's security requirements, failure modes, acceptance criteria, and test plan drop the
  refusal. `AC-2` is rewritten from "the author is refused" to "the author's approval succeeds and is
  flagged"; `tests/security/test_reviewer_is_not_author` becomes
  `tests/integration/test_self_approval_is_recorded`.
- `prope_release_author_review_blocked_total` is replaced by `prope_release_self_approval_total`. It is
  a fact counter, not an error counter, and no alert fires on it — alerting would reintroduce the
  refusal as a page.
- `approval.self_approved` is stored rather than derived, for the same reason as the evidence digest
  (A-074): it records what was true at decision time, and ownership of a revision's author field lives
  in another module.
- **The MVP's headline guarantee is unchanged.** "100% of non-break-glass releases carry an approval
  record" and "0 unapproved revisions reaching a release" (`00_context.md#success`) never depended on
  *who* approved. What this changes is the strength of the internal-control story, and the honest
  version of that story is now: Prope guarantees a release carries a recorded decision by someone
  holding the permission, and shows you when that someone was the author. The pitch must not claim
  more (`positioning.md` §7).
- If a workspace later needs segregation of duties for a compliance regime, `self_approved` is the
  field that shows whether it was already being observed in practice.
