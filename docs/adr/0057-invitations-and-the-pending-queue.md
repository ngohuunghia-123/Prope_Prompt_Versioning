# ADR-0057 — Invitations exist, and a code buys a place in a queue rather than a membership

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: user
**Module**: access-control (owns `workspace_invite`, `workspace_member`) and property-history
(records the five new events)
**Related**: A-007, A-014, A-020, A-045, A-071, A-110, A-113, A-116, A-117, A-144, A-151,
ADR-0021, ADR-0022, ADR-0035, ADR-0043, ADR-0045, ADR-0053, ADR-0054, ADR-0056, NFR-01, OQ-137

## Context

ADR-0056 gave a person a lobby to stand in. This ADR gives them a door.

The request was specific: a workspace tab that manages members — granting and revoking permission,
creating an invite code, or adding somebody by email address, *including an address with no account
yet* — and, for the code path, an administrator's approval before the joiner can see or watch
anything.

**A-071 says Prope has no outbound channel**, and that is not reversed here. Nothing sends mail. An
invitation is a row and a string somebody reads out; an email invitation is a *reservation* against
an address, claimed when that address next appears at the door.

## Decision

**One table, two kinds of invitation, and a third membership status.**

### The table

1. **`access.workspace_invite`** (revision 0022), tenant-policied like everything else, `SELECT`,
   `INSERT` and `UPDATE` only — **no `DELETE`**, for `api_key`'s reason: a deleted invitation would
   orphan the `invite_created` event that names it, in a table nothing can remove the event from.
   Revocation is a timestamp.

2. **`num_nonnulls(code_hash, invited_email) = 1`.** Exactly one kind per row, enforced by the
   engine rather than by the two call sites.

### The code

3. **Six characters from `[0-9A-Za-z]`, living one hour.** This was the user's decision, made against
   a recommendation for a longer self-describing string, and it is recorded rather than quietly
   softened: 62⁶ is 5.7 × 10¹⁰, about 35.7 bits, and the alphabet contains `O`/`0` and `l`/`1`/`I`,
   so a mistyped character is a refusal rather than a near-miss and a one-hour life means a shared
   code is usually regenerated per person. What was bought is a code somebody can say out loud.

4. **Four things make that survivable, and none of them is the hash.** The one-hour window; a
   redemption rate limit of ten attempts per actor and per source address per rolling fifteen minutes;
   redemption requiring a signed-in account, so a guesser must first register (itself rate-limited,
   and leaving a row); and — the load-bearing one — **a correct guess buys a pending membership,
   which sees nothing.**

5. **The lookup is a second `FOR SELECT` policy keyed on the presented digest**, not a fifth
   `SECURITY DEFINER` function. A lobby caller has no tenant, so `invite_redeem` admits rows where
   `code_hash = current_setting('app.invite_code_hash', true)` or
   `invited_email = current_setting('app.invite_email', true)`. An unfiltered `SELECT *` under that
   policy returns the one row the caller could already have named, or none. `uq_workspace_invite_code_hash`
   is globally unique across tenants, which is what makes a code resolve to a workspace at all —
   and is why the digest is unsalted (ADR-0021's argument, running the other way: a salt would make
   the lookup a scan).

### The queue

6. **`workspace_member.status` gains `pending`.** *"An active member with no roles"* was the
   alternative and is unsafe: `permissions.WORKSPACE_VISIBLE_ACTIONS` grants `prompt.read`,
   `suite.read` and `run.read` to **any** member when a prompt's `access_level` is `workspace`, so a
   role-less active member is already reading prompts. **Pending is not a weak active; it is a strong
   removed** — `may()` answers it exactly as it answers `removed`, and `enter_workspace` refuses it
   with the not-found a nonexistent workspace gets.

7. **Approval is the recorded human decision**, `POST /workspaces/{id}/members/{user_id}/approve`,
   and **the roles are the approver's**. The invitation's `grants_roles` pre-fills the form and binds
   nothing, because an hour can pass between creating a code and finding out who used it.

8. **Rejection moves the row to `removed` and keeps it.** A rejected person is indistinguishable from
   a removed one everywhere downstream, which is the point: `may()` already answers correctly for
   `removed`, and a fourth status would be a fourth thing every permission query has to know.

### The email seat

9. **`invited_email` reserves a seat for an address, whether or not anybody holds it.** A membership
   cannot exist before its user does — `workspace_member.user_id` is a foreign key — so the
   reservation lives on the invitation and `claim_email_invites` turns it into a membership.

10. **It grants outright, and does not queue.** An Admin naming one person is the same decision
    `POST /members` records; the queue exists for codes, where the workspace does not know who is
    holding one. The `member_added` event names the **inviting Admin** as its actor: the act being
    recorded is the invitation, and the arrival is when it took effect.

11. **The claim runs at two doors** — inside `register_account`, before the session is issued, so a
    single claimed membership takes the person straight in; and in the login route, after
    `sign_in` returns, so an Admin can invite somebody who **already has an account**. The second
    call is after rather than before because `sign_in` counts memberships to decide where to land and
    `sessions` cannot import `commands`; the visible cost is that such a person arrives on the
    chooser with the workspace on it, one click from where they were going. A cycle between those two
    modules was the alternative and is a worse thing to own than a click.

12. **The address is folded to lower case on the invitation and on the lookup, and nowhere else.**
    `access."user".email` keeps what the person typed, because the sign-in limiter is keyed on that
    string (`LoginRequest`).

### Permissions and refusals

13. **Everything an administrator does here is `workspace.manage_members`.** No 26th `Action`, no
    change to the seeded matrix. **`Owner` deliberately does not hold it**: `Owner` in Prope is a
    prompt-authoring role, and granting it member administration so that *"an Admin or Owner can
    approve"* would let any prompt author approve somebody and assign them `Admin` — self-promotion in
    two clicks, and the end of NFR-01's separation. The person who creates a workspace already holds
    `Admin` through `FOUNDER_ROLES`, so the intended user of that request is unaffected.

14. **One refusal covers every way a redemption can fail.** Unknown, expired, revoked, exhausted and
    rate-limited all answer `404 invite_not_redeemable`, byte for byte. A distinguishable *"expired"*
    would confirm that a workspace exists behind that string, turning a search into a two-phase one;
    a distinguishable *"rate-limited"* would tell a script how much budget it had left (ADR-0043's
    rule, applied to a second door).

15. **Re-presenting a code is not an error.** The membership is read before the invitation's liveness
    is judged, so a single-use code still answers the person who just redeemed it. Nothing is
    disclosed by that ordering: the extra answer goes only to somebody who is already a member or
    already in the queue, about themselves.

### The trail

16. **Five new history actions**, taking the registry from 32 to 37:
    `invite_created`, `invite_revoked` (`target_type = invite`, which is why `invite` joins
    `NEVER_PROMPT_SCOPED_TARGET_TYPES`), and `member_join_requested`, `member_join_approved`,
    `member_join_rejected` (`target_type = member`).

17. **`member_join_requested` is the only event access-control writes whose actor is not an
    administrator**, and it carries `invite_id` in its details — the only key that joins a suspicious
    membership back to the code that admitted it and to whoever created that code. The membership row
    cannot answer that: `added_by` on a self-requested join names the invitation's creator, not the
    request.

18. **`invite_created` carries no details at all.** The code is a credential and belongs in exactly
    one response body; the invited address is a personal identifier, and ADR-0054 §7 already made the
    argument about writing one of those into a table nothing can delete from.

## Consequences

**Prope now has a self-service door into an existing workspace**, which it did not before. That is
the point, and it is also the new attack surface: the two counters
`prope_access_control_invite_redeem_total{outcome}` and
`prope_access_control_invite_redeem_rate_limited_total{bucket}` exist so a search is visible, and the
redemption limiter has its **own** series rather than sharing sign-in's — an alert that pages for a
mistyped invitation code is an alert people silence.

**35.7 bits is the weakest secret in the product.** It is bounded by the four properties above rather
than by its own entropy, and if any of them is relaxed — a longer life, a higher limit, an
auto-approval — the code length has to be revisited in the same change. Recorded here so that a
future *"can we make codes last a day?"* meets this paragraph.

**A-020 is untouched.** No real corporate prompt enters the pilot on the strength of this, and
nothing here weakens the four non-negotiables: approval before production is a release-control
property and this is a membership one, and the two must not be conflated by a reader who sees the
word *approve* twice.

**The pilot gains an onboarding path that does not require an Admin to read a password aloud.**
A-110's flow survives beside it and is still the only one that creates an account for somebody.
