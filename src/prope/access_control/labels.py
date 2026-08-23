"""Opaque ids to the one label a person recognises, and **nothing else**.

Two lookups, both the same shape: `key_labels` names an api key, `user_emails`
names an author. Everything below argues the first; :func:`user_emails` inherits
the argument unchanged and its docstring says where it differs.

The prompt-detail Production tab answers *which of our products is calling this
prompt*. The ledger records `consumer_key_id`, an opaque id; the label a person
recognises — "Shopee checkout", "internal batch job" — is `access.api_key.name`,
which lives here.

**This widens who may read a key name, and the widening is the point of the
file.** Listing keys is `workspace.manage_keys` (an Admin act: it is the surface
that mints and revokes credentials), and neither owning a prompt nor holding a
grant on it confers that. Under that rule the Prompt Owner — the first persona in
the charter, the person who cannot write code — would read `key_01H8…` where the
product promises an app name, and the tab would be useless to exactly the reader
it was built for.

So the disclosure is made deliberately and bounded three ways rather than left to
whoever calls this:

1. **Name only.** No `last_four`, no `scope_model_names`, no `created_by`, no
   timestamps, no revocation state, and structurally no `key_hash` — the return
   type is `Mapping[str, str]`, so there is nowhere to put a second field. A
   caller cannot ask this function for more than it gives.
2. **Only ids the caller already holds.** There is no "list every key" form. The
   caller passes ids it read from call records it was already authorised to see,
   so the set of names it can learn is the set of integrations that called a
   prompt it may read. A key that never touched that prompt is unnameable
   through this path.
3. **Under the tenant policy.** No `workspace_id` predicate, deliberately: RLS is
   the filter, so an id belonging to another workspace resolves to nothing rather
   than to that workspace's label (ADR-0035, ADR-0045).

**The permission check stays with the caller**, as it does for every read
access-control serves: this module authorises subjects passed to it and never
reads one for itself. prompt-registry authorises `prompt.read` against the prompt
row before it has any ids to pass.

A missing id is simply absent from the result — a revoked key keeps its row and
therefore its name, which is what a historical traffic view needs, and an id with
no row at all (another workspace's, or one deleted by a future retention job)
leaves the caller to render the raw id.
"""

from collections.abc import Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: `= ANY(:key_ids)` rather than an `IN` list built by string formatting, which
#: `tests/architecture/test_no_sql_interpolation.py` forbids and which would also
#: reparse the statement for every distinct number of ids.
KEY_LABELS = text(
    """
    SELECT id, name
    FROM   access.api_key
    WHERE  id = ANY(:key_ids)
    """
)


async def key_labels(db: AsyncSession, key_ids: Sequence[str]) -> Mapping[str, str]:
    """The display name of each key named, on the caller's transaction.

    Takes the caller's `db` — like `may` and `visible_subject_filter`, and unlike
    the two authentication seams — so the labels come from the same snapshot as
    the traffic they annotate.

    An empty request is answered without a round trip, because the ordinary case
    for a prompt with no gateway traffic at all is a list of zero ids.
    """
    unique = sorted({key_id for key_id in key_ids if key_id})
    if not unique:
        return {}

    rows = (await db.execute(KEY_LABELS, {"key_ids": unique})).mappings().all()
    return {row["id"]: row["name"] for row in rows}


#: Same shape and same three bounds as `KEY_LABELS` above. `access."user"` is
#: quoted because `user` is a reserved word in SQL, and an unquoted `access.user`
#: parses as the `USER` function rather than as this table.
USER_EMAILS = text(
    """
    SELECT id, email
    FROM   access."user"
    WHERE  id = ANY(:user_ids)
    """
)


async def user_emails(db: AsyncSession, user_ids: Sequence[str]) -> Mapping[str, str]:
    """The email of each user named, on the caller's transaction.

    **The byline on a revision, and nothing else about the person.** The version
    rail answers *who saved this*, and `registry.revision.author_id` is an opaque
    id. The same three bounds as :func:`key_labels` apply and for the same
    reasons: email only — the return type has nowhere to put a second field — for
    ids the caller already holds, under the tenant policy rather than under a
    `workspace_id` predicate.

    **A missing id is absent from the result, and that is the ordinary case.**
    ADR-0054 tombstones the `access."user"` row of somebody who leaves while
    `author_id` survives as an opaque value, so a revision outlives the account
    that wrote it by design. The caller renders the id, or nothing, rather than
    asserting an email that no longer belongs to anyone.

    This exists so prompt-registry does not reach across a schema boundary to
    read it. Registry SQL that selected `access."user"` directly would work, and
    would be invisible to the import-graph architecture tests that police every
    other edge this module has.
    """
    unique = sorted({user_id for user_id in user_ids if user_id})
    if not unique:
        return {}

    rows = (await db.execute(USER_EMAILS, {"user_ids": unique})).mappings().all()
    return {row["id"]: row["email"] for row in rows}
