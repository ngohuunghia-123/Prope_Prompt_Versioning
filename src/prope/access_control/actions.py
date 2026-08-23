"""A-115's closed vocabulary, and the map joining it to the route table.

**There are two vocabularies in Prope and they answer different questions.**
Conflating them is the mistake this file exists to make impossible, so both are
named here even though only one is defined here.

``prope.session_auth.ManagementAction`` is the **route declaration** vocabulary.
Its members are module-prefixed (``call_ledger.price.create``,
``access_control.auth.login``) and there is exactly one per HTTP operation —
``tests/architecture/test_route_table.py`` asserts that bijection. It answers
*"what does this endpoint do"*, it is attached by a no-op dependency, and it
**checks nothing**.

:class:`Action` is the **permission** vocabulary — A-115's twenty-six strings,
byte-identical to ``ck_role_permission_action_values`` in revision 0006. It is
the only thing ``may()`` and ``access.role_permission.action`` accept. It answers
*"what may this actor do"*, and it is coarser on purpose: ``price.manage`` is one
permission over two call-ledger routes, because A-115 enumerates *permissions*
and the route table enumerates *operations*.

**Why they were not unified.** Renaming call-ledger's five shipped members onto
A-115's names would collapse ``price.create`` and ``price.read`` into one
declaration, and ``test_every_registered_action_is_declared_exactly_once`` would
then be asserting a bijection that no longer exists. Seeding
``role_permission`` with the prefixed strings instead would make the running
matrix disagree with A-115 and with INT-001's table, so ``GET
/api/v1/permissions`` would render something OQ-006's answer could not be
compared against — which is the endpoint's entire job.

So: two vocabularies, one **total** map, and a contract test that walks it.
:data:`ROUTE_ACTION` is the only place the two meet, and a route whose
declaration is missing from it fails at import rather than at request time.

**A third spelling exists and is not adopted.** ``interfaces.md``'s INT-001
table writes ``prompt.change_owner`` and ``prompt.change_access`` where A-115
writes ``prompt.transfer_owner`` and ``prompt.grant``. This file follows A-115,
because A-115 is what the seed and the ``CHECK`` are written from and what
``GET /api/v1/permissions`` renders. Raised as ``OQ-133`` rather than resolved by
picking a favourite.
"""

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from prope.session_auth import ManagementAction

__all__ = [
    "ACTIONS_BY_VALUE",
    "ROUTE_ACTION",
    "Action",
    "NoPermission",
    "parse_action",
]


class Action(StrEnum):
    """The closed action vocabulary. Twenty-seven members, and growing costs a migration.

    **Default-deny at the vocabulary level, not just at the matrix level**
    (A-115). A string-typed action means a typo, a renamed constant or a newly
    added feature can fall through to a branch nobody wrote — and every one of
    those failures is silent *in the allow direction*. Enumerating makes adding a
    feature require touching this list, which is the moment somebody decides who
    should hold it.

    That the list must be **edited** to grow is the feature, and it is why the
    same twenty-seven strings are also a database `CHECK`: a value that reaches
    `role_permission` from anywhere else is refused by the engine.

    Ordered as A-115 orders them, not alphabetically — the grouping is the
    argument, and re-sorting it would lose the shape (six prompt actions, four
    evaluation, five release, four provider, two workspace, two call-ledger
    admin, one account-level, and — since 2026-08-18 — one namespace-level).
    """

    PROMPT_READ = "prompt.read"
    PROMPT_CREATE = "prompt.create"
    PROMPT_EDIT = "prompt.edit"
    PROMPT_RETIRE = "prompt.retire"
    PROMPT_TRANSFER_OWNER = "prompt.transfer_owner"
    PROMPT_GRANT = "prompt.grant"
    REVISION_CREATE = "revision.create"

    SUITE_READ = "suite.read"
    SUITE_EDIT = "suite.edit"
    RUN_START = "run.start"
    RUN_READ = "run.read"

    REVISION_SUBMIT = "revision.submit"
    REVISION_APPROVE = "revision.approve"
    RELEASE_CREATE = "release.create"
    RELEASE_BREAK_GLASS = "release.break_glass"
    RELEASE_WITHDRAW = "release.withdraw"

    PROVIDER_CONFIGURE = "provider.configure"
    PROVIDER_ROTATE_CREDENTIAL = "provider.rotate_credential"
    PROVIDER_DISABLE = "provider.disable"
    CATALOGUE_READ = "catalogue.read"

    WORKSPACE_MANAGE_MEMBERS = "workspace.manage_members"
    WORKSPACE_MANAGE_KEYS = "workspace.manage_keys"

    PRICE_MANAGE = "price.manage"
    SPEND_CEILING_MANAGE = "spend_ceiling.manage"

    #: Added 2026-08-09 with ADR-0054. Deliberately **not** folded into
    #: `workspace.manage_members`: removing a person from a workspace is
    #: reversible and workspace-scoped, while tombstoning an account is
    #: irreversible and account-scoped, and one permission covering both would
    #: let a workspace admin erase a person who still works elsewhere.
    USER_TOMBSTONE = "user.tombstone"

    #: Added 2026-08-18 with ADR-0061 (A-160). The twenty-sixth, and deliberately
    #: **not** folded into `prompt.grant` — which sits in `OWNER_ACTIONS`, so the
    #: fold would let any prompt owner hand somebody a folder holding a thousand
    #: prompts. That is the escalation OQ-079 spent its length declining to create
    #: by accident, and creating it on purpose would be worse.
    #:
    #: It is in neither `OWNER_ACTIONS` nor `GRANT_ACTIONS`: owning a prompt says
    #: nothing about who should hold a folder, and a granted namespace must not be
    #: re-grantable onward by its recipient. That second clause is A-112's ceiling
    #: applied to the wider scope, and it is what stops a namespace grant becoming
    #: a way to distribute authority sideways.
    NAMESPACE_GRANT = "namespace.grant"

    #: Added 2026-08-20 with ADR-0067. The twenty-seventh, and the one that
    #: existed already under another name.
    #:
    #: `run.start` describes a probe accurately — *may spend workspace money
    #: dispatching against a revision* — and reusing it would have cost no
    #: vocabulary, no migration and no matrix decision. It is refused because
    #: this set is mapped to roles by `role_permission` ROWS: reuse means every
    #: role already holding `run.start` gains probe capability on the deploy that
    #: ships prompt-readiness, **with nobody deciding**. A minted action starts
    #: ungranted and somebody has to write the row.
    #:
    #: That the list must be EDITED to grow is the feature, and this is the
    #: clearest case of it in the file: the two permissions are so close that the
    #: only thing separating them is that one of them is new.
    PROBE_START = "probe.start"


#: Every member by its wire value. Built once, because `may()` resolves a string
#: on the hot path and `Action(value)` raises — which is the one thing A-115
#: forbids the unknown case from doing.
ACTIONS_BY_VALUE: Final[MappingProxyType[str, Action]] = MappingProxyType({member.value: member for member in Action})


def parse_action(action: Action | str) -> Action | None:
    """The action, or ``None`` if it is not in the vocabulary. **Never raises.**

    A-115 makes an unrecognised action a **deny**, not an error and not an allow.
    A parse that raised would turn a caller's typo into a 500 — which is a
    refusal, so it is safe, but it is a refusal that pages somebody and hides
    which action was wrong behind a stack trace. Returning ``None`` lets
    `may()` count it on ``unknown_action_total`` and deny quietly, which is what
    the alert `AccessControlUnknownAction` is watching for.
    """
    if isinstance(action, Action):
        return action
    return ACTIONS_BY_VALUE.get(action)


class NoPermission(StrEnum):
    """Why a route declares no :class:`Action`, as a value rather than a ``None``.

    Four routes in INT-029 check no permission, and each has a different reason.
    A plain ``None`` in :data:`ROUTE_ACTION` would make them all look like the
    same thing — and, worse, would make a route somebody *forgot* to map look
    like a deliberate exemption. A member of this enum is a sentence somebody
    wrote.
    """

    #: `POST /api/v1/auth/login` and `POST /api/v1/auth/register` — the two
    #: unauthenticated routes in Prope's management API, and there are no others.
    #: There is no actor yet, so there is nothing to authorise. Registration joins
    #: the list because A-071 forbids invitations and Prope has no outbound
    #: channel: without an open sign-up an install with no accounts has no way to
    #: acquire its first one.
    UNAUTHENTICATED = "unauthenticated"
    #: The actor is acting on their own account and on nothing else: sign out,
    #: change own password, read own session, list the workspaces they belong to,
    #: enter one of them, create one. A permission here would be a permission every
    #: actor must hold, which is a permission that means nothing — and one that
    #: could be revoked, locking somebody out of the change-password route A-110
    #: forces them through at first sign-in, or out of the chooser ADR-0056 sends
    #: them to when they belong to no workspace at all.
    SELF_SCOPED = "self_scoped"
    #: `GET /api/v1/permissions` renders the install-wide `(role, action)` matrix,
    #: which is a global table with no tenant column and no secret in it. Gating
    #: it would make the check that proves OQ-006's answer was applied readable
    #: only by the role the answer is about.
    PUBLIC_TO_MEMBERS = "public_to_members"


#: The one place the two vocabularies meet. **Total over `ManagementAction`**, and
#: `tests/contract/test_route_actions_map_onto_the_vocabulary.py` asserts the
#: totality — a route declaring a member that is absent here would mount fine and
#: then be unauthorisable, which is AC-10's failure wearing a passing test.
#:
#: call-ledger's five entries map onto A-115's two admin permissions and are the
#: reason this map is not an identity: `price.create` and `price.read` are two
#: operations under one permission, and `unpriced_worklist.read` is a third.
#: ADR-0018 means call-ledger never *calls* `may()` with them — the map is what
#: lets the route-table assertion in Phase 23 resolve every route in the product
#: to a permission anyway.
ROUTE_ACTION: Final[MappingProxyType[ManagementAction, Action | NoPermission]] = MappingProxyType(
    {
        # --- call-ledger, INT-028 -----------------------------------------
        ManagementAction.PRICE_CREATE: Action.PRICE_MANAGE,
        ManagementAction.PRICE_READ: Action.PRICE_MANAGE,
        ManagementAction.UNPRICED_WORKLIST_READ: Action.PRICE_MANAGE,
        ManagementAction.SPEND_CEILING_SET: Action.SPEND_CEILING_MANAGE,
        ManagementAction.RETENTION_SET: Action.SPEND_CEILING_MANAGE,
        ManagementAction.OBSERVABILITY_CONTENT_ACCESS_READ: Action.SPEND_CEILING_MANAGE,
        ManagementAction.OBSERVABILITY_CONTENT_ACCESS_SET: Action.SPEND_CEILING_MANAGE,
        # --- access-control, INT-029 --------------------------------------
        ManagementAction.AUTH_LOGIN: NoPermission.UNAUTHENTICATED,
        ManagementAction.AUTH_REGISTER: NoPermission.UNAUTHENTICATED,
        ManagementAction.AUTH_LOGOUT: NoPermission.SELF_SCOPED,
        ManagementAction.AUTH_PASSWORD: NoPermission.SELF_SCOPED,
        ManagementAction.AUTH_SESSION: NoPermission.SELF_SCOPED,
        # ADR-0056's two lobby routes. Both are `SELF_SCOPED` and neither could be
        # anything else.
        #
        # `WORKSPACE_LIST` reports the caller's OWN memberships. A permission over
        # that is a permission every actor must hold — which means nothing — and
        # one that could be revoked, stranding somebody in a lobby with no visible
        # way out of it.
        #
        # `WORKSPACE_ENTER` is the interesting one, because it looks like it wants
        # a permission and must not have one. The authority to enter a workspace IS
        # an active membership in it, checked in `sessions.enter_workspace` against
        # the row itself; a member with zero role bindings is a legitimate state
        # (A-110), so any `Action` gate here would refuse exactly the person an
        # Admin has just approved and not yet assigned. It is also the one route in
        # the product that names a workspace the session does not, so its refusal
        # is not-found rather than forbidden — and a permission-shaped gate would
        # have made a forbidden the natural thing to raise.
        ManagementAction.WORKSPACE_LIST: NoPermission.SELF_SCOPED,
        ManagementAction.WORKSPACE_ENTER: NoPermission.SELF_SCOPED,
        ManagementAction.WORKSPACE_CREATE: NoPermission.SELF_SCOPED,
        ManagementAction.MEMBER_LIST: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.MEMBER_ADD: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.MEMBER_REMOVE: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.MEMBER_ROLES_SET: Action.WORKSPACE_MANAGE_MEMBERS,
        # ADR-0057. Everything an administrator does to invitations and to the
        # pending queue is `workspace.manage_members`, and no 26th permission was
        # added for it.
        #
        # **Owner deliberately does not hold it**, and this is where that decision
        # bites: `Owner` in Prope is a prompt-authoring role (A-007), so granting it
        # `workspace.manage_members` so that "an Owner can approve" — the request
        # this feature came from — would let any prompt author approve a member and
        # assign them Admin, which is self-promotion by two clicks and the end of
        # NFR-01's separation. The person who creates a workspace already holds
        # Admin through `FOUNDER_ROLES`, so the intended user of that request is
        # unaffected.
        ManagementAction.INVITE_LIST: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.INVITE_CREATE: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.INVITE_REVOKE: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.MEMBER_APPROVE: Action.WORKSPACE_MANAGE_MEMBERS,
        ManagementAction.MEMBER_REJECT: Action.WORKSPACE_MANAGE_MEMBERS,
        # Redeeming is `SELF_SCOPED` for `WORKSPACE_ENTER`'s reason and one more of
        # its own: the caller is in the lobby, so there is no workspace to check a
        # permission in, and the authority they are exercising is possession of the
        # code rather than any standing they hold. What the code buys them is a
        # place in a queue, which is why it can be authorised by nothing at all.
        ManagementAction.INVITE_REDEEM: NoPermission.SELF_SCOPED,
        ManagementAction.GRANT_LIST: Action.PROMPT_READ,
        ManagementAction.GRANT_CREATE: Action.PROMPT_GRANT,
        ManagementAction.GRANT_REVOKE: Action.PROMPT_GRANT,
        ManagementAction.KEY_LIST: Action.WORKSPACE_MANAGE_KEYS,
        ManagementAction.KEY_CREATE: Action.WORKSPACE_MANAGE_KEYS,
        ManagementAction.KEY_REVOKE: Action.WORKSPACE_MANAGE_KEYS,
        # Widening a key's reach is the same permission as minting one, and not a
        # weaker one. The tempting alternative — letting anyone who may read a
        # prompt add it to a key's scope, since they can already see it — hands
        # every reader the ability to publish a prompt to an existing external
        # credential, which is a release by another name.
        ManagementAction.KEY_SCOPE_SET: Action.WORKSPACE_MANAGE_KEYS,
        ManagementAction.PERMISSION_MATRIX_READ: NoPermission.PUBLIC_TO_MEMBERS,
        ManagementAction.USER_TOMBSTONE: Action.USER_TOMBSTONE,
        # --- provider-access, INT-027 -------------------------------------
        #
        # Four permissions over ten operations, and the coarseness is A-115's.
        # Reading a configuration and reading its catalogue are one permission
        # (`catalogue.read`), because a configuration read returns no secret —
        # `last_four` is the only credential-derived value that crosses.
        # Deleting a configuration is `provider.disable`: A-096 makes the two
        # the same act with different finality, and a separate permission would
        # imply an Admin could hold one without the other.
        ManagementAction.PROVIDER_CREATE: Action.PROVIDER_CONFIGURE,
        ManagementAction.PROVIDER_LIST: Action.CATALOGUE_READ,
        ManagementAction.PROVIDER_READ: Action.CATALOGUE_READ,
        ManagementAction.PROVIDER_UPDATE: Action.PROVIDER_CONFIGURE,
        ManagementAction.PROVIDER_ROTATE_CREDENTIAL: Action.PROVIDER_ROTATE_CREDENTIAL,
        ManagementAction.PROVIDER_VERIFY: Action.PROVIDER_CONFIGURE,
        ManagementAction.PROVIDER_DELETE: Action.PROVIDER_DISABLE,
        ManagementAction.CATALOGUE_READ: Action.CATALOGUE_READ,
        ManagementAction.CATALOGUE_REFRESH: Action.PROVIDER_CONFIGURE,
        ManagementAction.CATALOGUE_ADD: Action.PROVIDER_CONFIGURE,
        # --- prompt-registry, INT-024 -------------------------------------
        #
        # Five permissions over ten operations, and the coarseness is A-115's
        # again. Everything that reads a prompt, its revisions, its diff or its
        # activity is one permission — `prompt.read` — because a grant confers
        # visibility of the prompt and everything hanging off it, and a reader
        # who could see the body but not the change summary would be a reader
        # who cannot review.
        #
        # `PROMPT_UPDATE` maps to the COARSEST of the three permissions that
        # route can need. `prompt.transfer_owner` and `prompt.grant` are checked
        # inside the handler, only when the field requiring them actually moves,
        # because this map is total over ManagementAction and a route has
        # exactly one entry — it answers "what must every caller of this route
        # hold", not "what might one of them need".
        ManagementAction.PROMPT_LIST: Action.PROMPT_READ,
        ManagementAction.PROMPT_CREATE: Action.PROMPT_CREATE,
        ManagementAction.PROMPT_READ: Action.PROMPT_READ,
        ManagementAction.PROMPT_UPDATE: Action.PROMPT_EDIT,
        ManagementAction.REVISION_TAGS_UPDATE: Action.PROMPT_EDIT,
        ManagementAction.PROMPT_RETIRE: Action.PROMPT_RETIRE,
        ManagementAction.REVISION_LIST: Action.PROMPT_READ,
        ManagementAction.REVISION_CREATE: Action.REVISION_CREATE,
        ManagementAction.REVISION_READ: Action.PROMPT_READ,
        # The playground turn, and the one prompt-registry operation that is not
        # a read of something already stored. `run.start` rather than
        # `prompt.read` because the act is spending provider money against this
        # prompt, which is exactly what an eval run does and exactly what that
        # permission already names. A Viewer may read a body; a Viewer may not
        # bill the workspace for it.
        ManagementAction.REVISION_TRIAL: Action.RUN_START,
        ManagementAction.DIFF_READ: Action.PROMPT_READ,
        ManagementAction.ACTIVITY_READ: Action.PROMPT_READ,
        # A grant confers visibility of the prompt and everything hanging off it,
        # and what it has served is one of those things — a reviewer who could see
        # the diff but not whether the released revision is actually being called
        # would be a reviewer working from half the evidence. Deliberately NOT a
        # permission of its own: `read_bodies` (A-040) is the permission that does
        # not exist yet, and it is about bodies, which this read cannot reach.
        ManagementAction.CALL_RECORD_LIST: Action.PROMPT_READ,
        ManagementAction.CALL_OBSERVABILITY_READ: Action.PROMPT_READ,
        ManagementAction.PROMPT_USAGE_READ: Action.PROMPT_READ,
        # The chain view, on the same permission and for the same reason. What a
        # prompt has served is part of the prompt; the order it served it in is
        # the same fact with the caller's correlation attached. The graph route
        # additionally drops every node whose own prompt fails this same check,
        # which is why one `prompt.read` on the entry point does not become a
        # read of prompts the actor cannot see.
        ManagementAction.CONVERSATION_LIST: Action.PROMPT_READ,
        ManagementAction.CONVERSATION_READ: Action.PROMPT_READ,
        # Folders: the three writes on `prompt.create`, the read on
        # `prompt.read`, and the coarseness of the writes is deliberate in the
        # other direction from `PROMPT_UPDATE`'s.
        #
        # A folder is a namespace with a label on it. No folder operation touches
        # a prompt, a revision, an approval or a release; delete is refused while
        # the folder holds anything, so it destroys nothing; and A-021 forbids
        # renaming the slug, so the address a consuming product calls is out of
        # reach from here. What is left is one capability — *may organise the
        # registry* — held by exactly the people who may put something in it.
        #
        # A `folder.create` permission of its own was the alternative. A-115's
        # vocabulary is closed and also a database CHECK, so a 26th member costs
        # a migration and a seed-matrix decision per role — bought to express a
        # role that organises without authoring, which is none of the three
        # people this product is for.
        #
        # `FOLDER_LIST` is the exception and it is `prompt.read`: the folder grid
        # IS the prompts screen, so gating it on `prompt.create` would hand a
        # Reviewer — who holds `prompt.read` and `revision.approve` and no
        # authoring permission at all — an empty page where the registry should
        # be. Its counts are already scoped by `visible_subject_filter`, so it
        # confers no visibility that `GET /prompts` did not.
        ManagementAction.FOLDER_LIST: Action.PROMPT_READ,
        ManagementAction.FOLDER_CREATE: Action.PROMPT_CREATE,
        ManagementAction.FOLDER_UPDATE: Action.PROMPT_CREATE,
        ManagementAction.FOLDER_DELETE: Action.PROMPT_CREATE,
        # Conversion performs the exact conditional check in its handler:
        # prompt.create for a new prompt, revision.create for an existing one.
        ManagementAction.PROMPT_CONVERT: Action.PROMPT_CREATE,
        # --- prompt-search -----------------------------------------------
        ManagementAction.PROMPT_SEARCH: Action.PROMPT_READ,
        # Ranking prompts the actor may already read, against text the actor
        # supplied. `prompt.read` for the same reason the search above is:
        # the result set is filtered by `visible_subject_filter`, so this
        # confers no visibility that a search box did not already.
        ManagementAction.PROMPT_SEARCH_SIMILAR: Action.PROMPT_READ,
        ManagementAction.PROMPT_INDEX_READ: Action.PROMPT_READ,
        ManagementAction.PROMPT_INDEX_TRIGGER: Action.PROMPT_EDIT,
        ManagementAction.PROMPT_INDEX_PREVIEW: Action.PROMPT_EDIT,
        ManagementAction.PROMPT_INDEX_DELETE: Action.PROMPT_EDIT,
        ManagementAction.PROMPT_INDEX_JOB_READ: Action.PROMPT_READ,
        # --- evaluation, INT-025 ------------------------------------------
        #
        # Four permissions over nine operations, and the split is BR-10's
        # rather than this map's: `suite.edit` is a DISTINCT permission from
        # `prompt.edit`, because the eval suite is the yardstick a revision is
        # measured with and an author who could move it could pass their own
        # prompt. `run.start` is separate from `run.read` for the same reason
        # in the other direction — starting a run spends the workspace's own
        # provider credit, and reading one does not.
        ManagementAction.EVAL_SUITE_LIST: Action.SUITE_READ,
        ManagementAction.EVAL_SUITE_CREATE: Action.SUITE_EDIT,
        ManagementAction.EVAL_SUITE_READ: Action.SUITE_READ,
        ManagementAction.EVAL_SUITE_VERSIONS: Action.SUITE_READ,
        ManagementAction.EVAL_SUITE_UPDATE: Action.SUITE_EDIT,
        ManagementAction.EVAL_RUN_START: Action.RUN_START,
        ManagementAction.EVAL_RUN_READ: Action.RUN_READ,
        ManagementAction.EVAL_RUN_LIST: Action.RUN_READ,
        ManagementAction.EVAL_RUN_CASES: Action.RUN_READ,
        ManagementAction.EVAL_CASE_TRACE: Action.RUN_READ,
        ManagementAction.COMPARISON_READ: Action.RUN_READ,
        ManagementAction.DATASET_LIST: Action.SUITE_READ,
        ManagementAction.DATASET_ATTACHMENT_LIST: Action.SUITE_READ,
        ManagementAction.DATASET_ATTACHMENT_REPLACE: Action.SUITE_EDIT,
        ManagementAction.EVAL_RUN_START_FROM_ATTACHMENTS: Action.RUN_START,
        # --- evaluation, the dataset library (step 4a) --------------------
        #
        # **These nine were declared and never mapped**, which left every one of
        # them unauthorisable while mounting perfectly — AC-10's failure wearing
        # a passing test, and the exact hole this map exists to close. Added
        # 2026-08-20 alongside prompt-readiness, whose own five entries are what
        # made the gap visible.
        #
        # The permissions are the ones ``ManagementAction``'s own block already
        # names, so nothing here is a new decision:
        #
        # A dataset is the reusable library object somebody picks; a suite is the
        # immutable per-prompt thing a run reads. Reading the library is
        # `suite.read` and authoring in it is `suite.edit`, asked about the
        # WORKSPACE rather than about a prompt — a dataset belongs to no prompt,
        # so there is no per-subject grant to consult and role bindings alone
        # decide. Deliberately NOT new members of `Action`: that vocabulary is
        # closed, growing it costs a migration and a matrix row, and *"may author
        # yardsticks here"* is the permission this already is.
        #
        # `dataset.draft` is the prompt-scoped one — drafting reads a prompt body
        # — and it is `suite.edit` for BR-10's reason: an author who could move
        # the yardstick could pass their own prompt, so drafting cannot be a way
        # around the permission that governs authoring one.
        #
        # `dataset_attachment.replace` is `suite.edit` because choosing what
        # measures a prompt is a suite-authoring act, even though no suite is
        # written until a run.
        #
        # `eval_run.start_from_attachments` is `run.start` exactly as
        # `eval_run.start` is; where the suite list comes from is not an
        # authorisation distinction.
        ManagementAction.DATASET_READ: Action.SUITE_READ,
        ManagementAction.DATASET_CREATE: Action.SUITE_EDIT,
        ManagementAction.DATASET_UPDATE: Action.SUITE_EDIT,
        ManagementAction.DATASET_DELETE: Action.SUITE_EDIT,
        ManagementAction.DATASET_DRAFT: Action.SUITE_EDIT,
        # --- release-control, INT-026 -------------------------------------
        #
        # FIVE DISTINCT PERMISSIONS over eleven operations, and the split is a
        # non-negotiable constraint rather than this map's taste: edit, review
        # and release are separated (00_context.md#constraints, A-007), and
        # break-glass and withdraw are their own permissions rather than
        # capabilities that come free with release — an escape hatch everyone
        # holds is not an escape hatch (A-009), and withdraw takes a consuming
        # product's feature offline (A-069, ADR-0009).
        #
        # Reading the review screen and the release log is `prompt.read`, for
        # prompt-registry's reason one block up: a grant confers visibility of
        # the prompt and everything hanging off it, and a reviewer who could see
        # the diff but not the release log would be a reviewer who cannot
        # review.
        #
        # `approve_and_release` records the COARSER of the two it needs. Both
        # are always required; `release.create` is checked inside the handler,
        # and the refusal names whichever one is missing (A-076).
        ManagementAction.RELEASE_SUBMIT: Action.REVISION_SUBMIT,
        ManagementAction.RELEASE_REVIEW_READ: Action.PROMPT_READ,
        ManagementAction.RELEASE_APPROVE: Action.REVISION_APPROVE,
        ManagementAction.RELEASE_REQUEST_CHANGES: Action.REVISION_APPROVE,
        ManagementAction.RELEASE_APPROVE_AND_RELEASE: Action.REVISION_APPROVE,
        ManagementAction.RELEASE_CREATE: Action.RELEASE_CREATE,
        ManagementAction.RELEASE_LIST: Action.PROMPT_READ,
        ManagementAction.RELEASE_BREAK_GLASS: Action.RELEASE_BREAK_GLASS,
        ManagementAction.RELEASE_WITHDRAW: Action.RELEASE_WITHDRAW,
        ManagementAction.RELEASE_REVIEW_TASK_LIST: Action.PROMPT_READ,
        ManagementAction.RELEASE_REVIEW_TASK_CLOSE: Action.REVISION_APPROVE,
        # --- chat-orchestrator --------------------------------------------
        #
        # `prompt.read` for the four read operations, for `prompt_search`'s
        # reason two blocks up: the assistant runs behind the same
        # `visible_subject_filter` the search box does, so talking to it confers
        # no visibility a search already did. A conversation is additionally
        # filtered to its own actor in the repository — that is ownership, not a
        # permission, and there is deliberately no member of `Action` for it.
        #
        # `chat.pipeline.read` is the fourth, and it is the odd one: it reads no
        # row at all. It renders `domain.TOOLS`, which is a build-time constant,
        # so there is nothing for a permission to protect and `NoPermission`
        # would be defensible. `prompt.read` anyway, because the tool catalogue
        # names what the assistant can do to prompts, and a signed-in actor who
        # may not read a prompt has no use for the shape of the machine that
        # reads them. The cheaper answer would be reversible; this one does not
        # need to be.
        #
        # `chat.action.decide` maps to `prompt.create` and the handler performs
        # the exact conditional check the same way `PROMPT_CONVERT` does: a
        # proposed `create_prompt` needs `prompt.create` and a proposed
        # `create_revision` needs `revision.create`, resolved in
        # `tools.execute_*` against the row it has just read. This map answers
        # *"what must every caller of this route hold"*, a route has exactly one
        # entry, and the coarser of the two is what goes here (A-076's shape,
        # the same one `RELEASE_APPROVE_AND_RELEASE` uses one block up).
        ManagementAction.CHAT_MESSAGE_SEND: Action.PROMPT_READ,
        ManagementAction.CHAT_MESSAGE_SEND_STREAM: Action.PROMPT_READ,
        ManagementAction.CHAT_ACTION_DECIDE: Action.PROMPT_CREATE,
        ManagementAction.CHAT_CONVERSATION_LIST: Action.PROMPT_READ,
        ManagementAction.CHAT_CONVERSATION_READ: Action.PROMPT_READ,
        ManagementAction.CHAT_MESSAGE_FEEDBACK: Action.PROMPT_READ,
        ManagementAction.CHAT_PIPELINE_READ: Action.PROMPT_READ,
        # --- prompt-ingestion ---------------------------------------------
        # Reads reveal only actor-owned batch staging under workspace RLS.
        # Write-shaped routes map coarsely to prompt.create and perform the
        # exact create/revision permission check at commit time.
        ManagementAction.INGESTION_BATCH_CREATE: Action.PROMPT_CREATE,
        ManagementAction.INGESTION_BATCH_READ: Action.PROMPT_READ,
        ManagementAction.INGESTION_ITEM_LIST: Action.PROMPT_READ,
        ManagementAction.INGESTION_ITEM_UPDATE: Action.PROMPT_CREATE,
        ManagementAction.INGESTION_ITEM_RETRY: Action.PROMPT_CREATE,
        ManagementAction.INGESTION_PROPOSAL_CREATE: Action.PROMPT_CREATE,
        ManagementAction.INGESTION_PROPOSAL_DECIDE: Action.PROMPT_CREATE,
        # --- access-control, namespace authority (ADR-0061) ----------------
        #
        # The LIST maps to `prompt.read` and the two writes to `namespace.grant`,
        # which is the asymmetry ADR-0061 argues for: seeing who holds a folder
        # is part of seeing the folder, and handing somebody every prompt in it —
        # including the ones nobody has written yet — is not. A-160 records why
        # `prompt.grant` could not be reused: it is bounded by the row it names
        # and this is bounded by nothing, so one member covering both would make
        # the vocabulary unable to express "may share this prompt, may not share
        # the folder", which is the distinction the whole ADR exists to draw.
        ManagementAction.NAMESPACE_GRANT_LIST: Action.PROMPT_READ,
        ManagementAction.NAMESPACE_GRANT_CREATE: Action.NAMESPACE_GRANT,
        ManagementAction.NAMESPACE_GRANT_REVOKE: Action.NAMESPACE_GRANT,
        # --- prompt-observation, INT-035 (ADR-0060, ADR-0061) --------------
        #
        # All seven map to `prompt.read`, and the handler asks it about the
        # observation's NAMESPACE (SR-1). No new permission and no borrowed one.
        #
        # The four writes map here too. They are acts on an INVENTORY, not on a
        # prompt: `observation.adopted` records that prompt-registry created
        # something through its own routes under its own permissions, and the
        # other three remove text somebody's product sent by accident. Requiring
        # `prompt.create` for them — which an earlier draft of this module did —
        # made a LOW-privilege action grant the widest read in the product, which
        # is the inversion ADR-0061 fixes.
        ManagementAction.OBSERVATION_LIST: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_READ: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_PROPOSAL: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_ADOPTED: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_DISMISSED: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_REDACTED: Action.PROMPT_READ,
        ManagementAction.OBSERVATION_DELETE: Action.PROMPT_READ,
        # --- prompt-readiness, INT-038..INT-042 (ADR-0067) ----------------
        #
        # Four permissions over five operations, and only `probe.start` is new.
        # ManagementAction's own block carries the per-route reasoning; what
        # belongs here is why the coarseness falls the way it does.
        #
        # The two reads are `prompt.read` for prompt-registry's reason. The rule
        # CATALOGUE read is `prompt.read` too and could defensibly be
        # `PUBLIC_TO_MEMBERS` — it reads no row and names no prompt, like
        # `GET /api/v1/permissions`. It is gated anyway because the catalogue is
        # a list of what Prope looks for in a prompt, and a signed-in actor who
        # may not read a prompt has no use for it. The cheaper answer would be
        # reversible; this one does not need to be.
        #
        # `case_drafts.create` maps to `suite.edit` rather than to a new action,
        # landing it on exactly the permission `evaluation.dataset.draft`
        # already holds — the same act through a different door.
        ManagementAction.READINESS_CARD_READ: Action.PROMPT_READ,
        ManagementAction.READINESS_RULES_READ: Action.PROMPT_READ,
        ManagementAction.READINESS_PROBE_START: Action.PROBE_START,
        ManagementAction.READINESS_CASE_DRAFTS: Action.SUITE_EDIT,
        ManagementAction.READINESS_DISMISSAL_CREATE: Action.PROMPT_EDIT,
        # prompt-improvement (ADR-0068). Six routes, four actions, none minted.
        # `proposal.accept` is `revision.create` and not `prompt.edit`: the route
        # writes no revision, and it hands back a body destined for one — gating
        # it lower than the act it prefills would be a permission gap wearing a
        # read's clothes. `schedule.write` is `spend_ceiling.manage` because
        # enabling a recurring provider charge is a spending decision before it
        # is an authoring one.
        ManagementAction.IMPROVEMENT_INBOX_READ: Action.PROMPT_READ,
        ManagementAction.IMPROVEMENT_PROMPT_FINDINGS_READ: Action.PROMPT_READ,
        ManagementAction.IMPROVEMENT_FINDING_DISMISS: Action.PROMPT_EDIT,
        ManagementAction.IMPROVEMENT_PROPOSAL_ACCEPT: Action.REVISION_CREATE,
        ManagementAction.IMPROVEMENT_PROPOSAL_DISMISS: Action.PROMPT_EDIT,
        ManagementAction.IMPROVEMENT_SCHEDULE_READ: Action.SPEND_CEILING_MANAGE,
        ManagementAction.IMPROVEMENT_SCHEDULE_WRITE: Action.SPEND_CEILING_MANAGE,
        # Agent runs never broaden the underlying capability. Creation can
        # schedule provider work and therefore takes run.start; list/read are
        # actor-owned records, and the lifecycle summary follows prompt.read.
        ManagementAction.AGENT_RUN_CREATE: Action.RUN_START,
        ManagementAction.AGENT_RUN_LIST: Action.PROMPT_READ,
        ManagementAction.AGENT_RUN_READ: Action.PROMPT_READ,
        ManagementAction.AGENT_RUN_ACKNOWLEDGE: Action.PROMPT_READ,
        ManagementAction.LIFECYCLE_SUMMARY_READ: Action.PROMPT_READ,
        ManagementAction.ANNOTATION_LIST: Action.PROMPT_READ,
        ManagementAction.ANNOTATION_WRITE: Action.PROMPT_EDIT,
    }
)
