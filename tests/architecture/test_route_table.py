"""The assembled route table, asserted rather than described.

**This is the single-module form of assertions that cannot run in their full
form until Phase 23.** AC-10 (*"every route declares an action from the
vocabulary"*) and prompt-registry's route-uniqueness rule are both properties of
the **assembled** table — what is mounted in total, once every module has had its
say — and seven of the eight modules do not exist yet. PITFALLS § 5 records that
they *"cannot actually run until every module is mounted — i.e. not before phase
23"*. So this file asserts them over the one module that is mounted, using
helpers (``prope.session_auth.assembled_routes``, ``declared_action``,
``declares_session``) that live in the shared module precisely so **Phase 23
extends a test rather than inventing one**.

**CL-10's full claim is Phase 3's and its cross-module form is Phase 23's.** This
phase's obligation is narrower and entirely negative: do not mount a route that
would fail either. The OpenAPI walk below is that floor.

**D-13's explicit composition is what makes any of this writable.** A route that
could appear because a file was named a certain way is the shape these assertions
exist to refuse — the test would be checking a list the discovery mechanism also
produced. ``prope.app`` imports one router by name and includes it, and a
structural assertion here says so.
"""

import ast
import inspect
from pathlib import Path

from fastapi import FastAPI

import prope.app
import prope.worker
from prope.app import app
from prope.session_auth import (
    MANAGEMENT_ACTIONS,
    assembled_routes,
    declared_action,
    declares_action,
    declares_session,
)
from tests.integration._asgi import call

#: **The whole table, as literal strings.** INT-028's five, INT-029's sixteen,
#: INT-030's two, plus Phase 3's ``/metrics`` (D-39). Written out rather than
#: derived, because a test that computed its expectation from the application
#: would pass whatever the application happened to mount — which is the failure
#: mode this list exists to catch. An extra route fails here as loudly as a
#: missing one.
#:
#: ``POST|GET /api/v1/prices`` is one line in ``interfaces.md`` and two paths;
#: INT-028's own text settles the count by saying *"5 routes"* beside four bullet
#: lines. Every count in this file is a **path** count.
#:
#: **``/metrics`` is the one entry here that no lock file's ``apis.exposes``
#: block declares.** ``docs/architecture/interfaces.md`` says in as many words
#: that the line *"should gain an `exposes` line during step 6"*; step 6 ran and
#: did not add it. The surface ships with the deviation declared in
#: ``docs/brainstorm/open_questions/OQ-026.md``, never by editing the spec.
#:
#: **Phase 7 added access-control's sixteen and the count assertions moved with
#: them.** INT-029's own text says *"15 routes"* and the lock file says the
#: tombstone took it *"from 14 to 15"*; neither number matches an enumeration of
#: the route list either document prints. Sixteen is what is served, and
#: ``OQ-134`` carries the discrepancy rather than the spec being edited.
EXPECTED_ROUTES = frozenset(
    {
        # call-ledger, INT-028
        ("POST", "/api/v1/prices"),
        ("GET", "/api/v1/prices"),
        ("GET", "/api/v1/prices/unpriced"),
        ("PUT", "/api/v1/workspaces/{id}/spend-ceiling"),
        ("PUT", "/api/v1/workspaces/{id}/retention"),
        ("GET", "/api/v1/workspaces/{id}/observability-content-access"),
        ("PUT", "/api/v1/workspaces/{id}/observability-content-access"),
        # Durable prompt ingestion: stage, review, resolve, and confirm.
        ("POST", "/api/v1/import-batches"),
        ("GET", "/api/v1/import-batches/{batch_id}"),
        ("GET", "/api/v1/import-batches/{batch_id}/items"),
        ("PATCH", "/api/v1/import-batches/{batch_id}/items/{item_id}"),
        ("POST", "/api/v1/import-batches/{batch_id}/retry"),
        ("POST", "/api/v1/import-batches/{batch_id}/commit-proposals"),
        ("POST", "/api/v1/action-proposals/{proposal_id}/decision"),
        # Persistent background work and the lifecycle decision summary. Agent
        # runs expose only typed nodes and evidence references, never raw bodies.
        ("POST", "/api/v1/agent-runs"),
        ("GET", "/api/v1/agent-runs"),
        ("GET", "/api/v1/agent-runs/{run_id}"),
        ("POST", "/api/v1/agent-runs/{run_id}/acknowledge"),
        ("GET", "/api/v1/prompts/{prompt_id}/lifecycle-summary"),
        # access-control, INT-029
        ("POST", "/api/v1/auth/login"),
        # ADR-0052's SPA added the next two. `auth/session` because an HttpOnly
        # cookie is invisible to the script it authorises, so the client must ask
        # rather than look; `auth/register` because A-071 forbids invitations and
        # every other door into the product was behind a door.
        ("POST", "/api/v1/auth/register"),
        ("GET", "/api/v1/auth/session"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/password"),
        # ADR-0056's two lobby routes, and OQ-137's picker. Both sit under
        # `/auth` rather than `/workspaces` because both are facts about the
        # SESSION's owner: the list is their own memberships, and the enter is
        # the only route after sign-in that sets the session cookie. A session may
        # now name no workspace at all, so these are the two things a person can
        # do while belonging nowhere — besides creating one.
        ("GET", "/api/v1/auth/workspaces"),
        ("POST", "/api/v1/auth/workspaces/{workspace_id}/enter"),
        # ADR-0056's redemption, and the third route under `/auth` for the lobby's
        # reason: the caller is in no workspace and the workspace is discovered
        # from the code rather than named in the path, so there is nothing for
        # `path_workspace` to check.
        ("POST", "/api/v1/auth/invites/redeem"),
        ("POST", "/api/v1/workspaces"),
        ("GET", "/api/v1/workspaces/{id}/members"),
        ("POST", "/api/v1/workspaces/{id}/members"),
        ("DELETE", "/api/v1/workspaces/{id}/members/{user_id}"),
        ("PUT", "/api/v1/workspaces/{id}/members/{user_id}/roles"),
        # ADR-0056's human gate, and the reason a redeemed code is not a
        # membership. Two routes rather than one `PUT .../status`, because the
        # two write different history events and an audit asks *"who let this
        # person in"* — a status field would have made both answers one row.
        ("POST", "/api/v1/workspaces/{id}/members/{user_id}/approve"),
        ("POST", "/api/v1/workspaces/{id}/members/{user_id}/reject"),
        # The invitations screen. `DELETE` is the verb and an `UPDATE` is what
        # happens: revision 0022 withholds `DELETE` on `workspace_invite` for
        # `api_key`'s reason, so revocation is a timestamp.
        ("GET", "/api/v1/workspaces/{id}/invites"),
        ("POST", "/api/v1/workspaces/{id}/invites"),
        ("DELETE", "/api/v1/workspaces/{id}/invites/{invite_id}"),
        ("GET", "/api/v1/prompts/{prompt_id}/grants"),
        ("POST", "/api/v1/prompts/{prompt_id}/grants"),
        ("DELETE", "/api/v1/prompts/{prompt_id}/grants/{user_id}"),
        # ADR-0061's namespace grants: the same three operations one scope up.
        # No `owner_id` / `access_level` query parameters, because a namespace has
        # neither and there is therefore nothing here for a browser to forge —
        # OQ-139's surface does not extend to this pair.
        ("GET", "/api/v1/namespaces/{namespace}/grants"),
        ("POST", "/api/v1/namespaces/{namespace}/grants"),
        ("DELETE", "/api/v1/namespaces/{namespace}/grants/{user_id}"),
        ("GET", "/api/v1/workspaces/{id}/keys"),
        ("POST", "/api/v1/workspaces/{id}/keys"),
        ("DELETE", "/api/v1/workspaces/{id}/keys/{key_id}"),
        # Widening one key's scope. A separate route from key creation because
        # key scope is exact-match default-deny with no wildcard, so granting a
        # prompt to an existing integration is its own recorded act — it appends
        # an `api_key_scope_set` history row. Added with the code-snippet screen
        # and missing from this list until step 6 walked the table.
        ("PUT", "/api/v1/workspaces/{id}/keys/{key_id}/scope"),
        ("GET", "/api/v1/permissions"),
        ("POST", "/api/v1/users/{user_id}/tombstone"),
        # provider-access, INT-027
        ("POST", "/api/v1/providers"),
        ("GET", "/api/v1/providers"),
        ("GET", "/api/v1/providers/{provider_id}"),
        ("PATCH", "/api/v1/providers/{provider_id}"),
        ("DELETE", "/api/v1/providers/{provider_id}"),
        ("POST", "/api/v1/providers/{provider_id}/credential"),
        ("POST", "/api/v1/providers/{provider_id}/verify"),
        ("GET", "/api/v1/providers/{provider_id}/models"),
        ("POST", "/api/v1/providers/{provider_id}/models"),
        ("POST", "/api/v1/providers/{provider_id}/models/refresh"),
        # prompt-registry, INT-024
        ("GET", "/api/v1/prompts"),
        ("POST", "/api/v1/prompts"),
        ("GET", "/api/v1/prompts/{prompt_id}"),
        ("GET", "/api/v1/prompts/by-model-name/{namespace}/{name}"),
        ("PATCH", "/api/v1/prompts/{prompt_id}"),
        ("POST", "/api/v1/prompts/{prompt_id}/retire"),
        ("GET", "/api/v1/prompts/{prompt_id}/revisions"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions"),
        ("PATCH", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/tags"),
        ("GET", "/api/v1/revisions/{version_id}"),
        # The playground's one turn against a revision, streamed back over the
        # session. It exists because the gateway serves released revisions only —
        # a database constraint — so a Draft has no other way to be tried. It
        # declares `run.start` and not `prompt.read`: what it does is spend
        # provider money. Missing from this list until step 6 walked the table.
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/trials"),
        ("GET", "/api/v1/prompts/{prompt_id}/diff"),
        ("GET", "/api/v1/prompts/{prompt_id}/activity"),
        # ADR-0055. Call **metadata** for one prompt, behind `prompt.read`.
        # ADR-0018's no-read-path rule is about `ledger.call_body` and is
        # untouched; it says of the rest that "metadata is unaffected ... it has
        # readers". This is the reader, and it is mounted here rather than in
        # call-ledger because that module cannot check a permission.
        ("GET", "/api/v1/prompts/{prompt_id}/call-records"),
        ("GET", "/api/v1/prompts/{prompt_id}/call-records/{call_id}/observability"),
        # The same rows counted instead of listed, for the Production tab. Same
        # module, same `prompt.read`, same metadata-only rule — and the one route
        # in prompt-registry that reads an `access.api_key` name, bounded at
        # `access_control.labels`.
        ("GET", "/api/v1/prompts/{prompt_id}/usage"),
        # The customer's own chain, assembled from those same metadata rows by a
        # correlation id their application supplied. Two routes: the conversations
        # a prompt took part in, and one of them as a graph. Mounted here for
        # `/call-records`' reason, and scoped per-prompt for the same one — there
        # is no workspace-wide form of either, because a list of every
        # conversation would name conversations that ran through private prompts.
        ("GET", "/api/v1/prompts/{prompt_id}/conversations"),
        ("GET", "/api/v1/prompts/{prompt_id}/conversations/{conversation_id}"),
        # Human labels are stored against real call metadata. The write remains
        # prompt-scoped so the same visibility and edit checks protect it.
        ("GET", "/api/v1/annotations"),
        ("PUT", "/api/v1/prompts/{prompt_id}/call-records/{call_id}/annotation"),
        # Folders. Four operations across two paths, and not part of INT-024:
        # a folder is `prompt_property.namespace` with a display label beside it,
        # mounted here because this is the module that owns the column. The
        # write trio declares `prompt.create`; `GET` declares `prompt.read`,
        # because the folder grid is the prompts screen and a Reviewer holds no
        # authoring permission.
        ("GET", "/api/v1/folders"),
        ("POST", "/api/v1/folders"),
        ("PATCH", "/api/v1/folders/{slug}"),
        ("DELETE", "/api/v1/folders/{slug}"),
        # prompt-search
        ("GET", "/api/v1/prompts/search"),
        # The import screen's duplicate check. A POST because its input is a
        # whole prompt body and `?q=` caps at 500 characters; literal rather
        # than a `{prompt_id}` variant because the body being checked does not
        # exist yet — that is the point of checking it.
        ("POST", "/api/v1/prompts/search/similar"),
        ("GET", "/api/v1/prompts/{prompt_id}/index"),
        ("POST", "/api/v1/prompts/{prompt_id}/index"),
        ("GET", "/api/v1/prompts/{prompt_id}/index/preview"),
        ("DELETE", "/api/v1/prompts/{prompt_id}/index"),
        ("GET", "/api/v1/prompt-search/jobs/{job_id}"),
        ("POST", "/api/v1/prompt-conversions"),
        # evaluation, INT-025
        ("GET", "/api/v1/prompts/{prompt_id}/eval-suites"),
        ("POST", "/api/v1/prompts/{prompt_id}/eval-suites"),
        ("GET", "/api/v1/eval-suites/{suite_id}"),
        ("PUT", "/api/v1/eval-suites/{suite_id}"),
        ("GET", "/api/v1/prompts/{prompt_id}/eval-suites/{name}/versions"),
        ("POST", "/api/v1/prompts/{prompt_id}/eval-runs"),
        # The GET that POST never had. Every other run read needs a `run_id`,
        # which is no use to a screen opening on a prompt: the Eval tab has to
        # ask what has run against this before it knows any id.
        ("GET", "/api/v1/prompts/{prompt_id}/eval-runs"),
        ("GET", "/api/v1/eval-runs/{run_id}"),
        ("GET", "/api/v1/eval-runs/{run_id}/cases"),
        ("GET", "/api/v1/eval-runs/{run_id}/cases/{case_result_id}/trace"),
        ("GET", "/api/v1/prompts/{prompt_id}/comparison"),
        # evaluation datasets, step 4a. A dataset is the reusable library
        # object; a suite is the immutable per-prompt thing a run reads. The
        # attachment routes are the join, and the PUT carries the whole
        # tick-state rather than a POST/DELETE pair, because a builtin id
        # (`builtin:<slug>@<n>`) in a path segment is a URL-encoding trap.
        ("GET", "/api/v1/datasets"),
        ("GET", "/api/v1/prompts/{prompt_id}/dataset-attachments"),
        ("PUT", "/api/v1/prompts/{prompt_id}/dataset-attachments"),
        ("POST", "/api/v1/prompts/{prompt_id}/eval-runs/from-attachments"),
        # Step 4b made the library writable. `{dataset_id}` carries both id
        # shapes — `dst_<ULID>` and `builtin:<slug>@<n>` — and the colon and at
        # sign are legal in a path segment, so no encoding scheme is invented
        # here; the write routes simply refuse a builtin as read-only.
        ("POST", "/api/v1/datasets"),
        ("GET", "/api/v1/datasets/{dataset_id}"),
        ("PUT", "/api/v1/datasets/{dataset_id}"),
        ("DELETE", "/api/v1/datasets/{dataset_id}"),
        ("POST", "/api/v1/prompts/{prompt_id}/datasets/draft"),
        # release-control, INT-026
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/submit"),
        ("GET", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/review"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/approve"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/request-changes"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/approve-and-release"),
        ("POST", "/api/v1/prompts/{prompt_id}/releases"),
        ("GET", "/api/v1/prompts/{prompt_id}/releases"),
        ("POST", "/api/v1/prompts/{prompt_id}/releases/break-glass"),
        ("POST", "/api/v1/prompts/{prompt_id}/releases/withdraw"),
        ("GET", "/api/v1/review-tasks"),
        ("POST", "/api/v1/review-tasks/{task_id}/close"),
        # chat-orchestrator, and the only
        # module prefix no other module shares: `/api/v1/chat/*` is owned
        # outright, so the supervisor's reach never depended on winning a
        # registration race against `/prompts/{prompt_id}`.
        ("POST", "/api/v1/chat/messages"),
        ("POST", "/api/v1/chat/messages/stream"),
        ("POST", "/api/v1/chat/messages/{message_id}/feedback"),
        ("POST", "/api/v1/chat/actions/{action_id}"),
        ("GET", "/api/v1/chat/conversations"),
        ("GET", "/api/v1/chat/conversations/{conversation_id}"),
        # The shape of the pipeline, for the trace graph. The one route in this
        # module that reads no row: it renders `domain.TOOLS` and is identical
        # for every actor in every workspace.
        ("GET", "/api/v1/chat/pipeline"),
        # prompt-observation, INT-035 (ADR-0060). Seven operations over four
        # paths, and a module prefix no other module shares: `/api/v1/observations`
        # is owned outright.
        #
        # `redacted` and the `DELETE` are both here on purpose — SR-4 requires a
        # redact route AND a delete route from the first commit, before the
        # retention policy that would cover them exists. This is the first table
        # in Prope holding customer text nobody submitted, and the answer to "take
        # that one out" must not be a migration.
        ("GET", "/api/v1/observations"),
        ("GET", "/api/v1/observations/{observation_id}"),
        ("POST", "/api/v1/observations/{observation_id}/proposal"),
        ("POST", "/api/v1/observations/{observation_id}/adopted"),
        ("POST", "/api/v1/observations/{observation_id}/dismissed"),
        ("POST", "/api/v1/observations/{observation_id}/redacted"),
        ("DELETE", "/api/v1/observations/{observation_id}"),
        # prompt-readiness, INT-038..INT-042 (ADR-0067). Five operations. Four
        # of them sit under `/api/v1/prompts/{prompt_id}`, which five modules
        # now share — `test_the_assembled_table_has_no_duplicate_operation` is
        # what keeps that safe rather than the fact that nobody has collided.
        #
        # **The GET on `/readiness` writes.** It is the only read in Prope that
        # does, and SR-1 is why: release-control is forbidden in both directions,
        # so the reviewer's frozen copy cannot be written by a submit hook, and
        # the first card read of a revision past `Draft` writes it instead. The
        # route table is where somebody would first notice that oddity, so it is
        # recorded here rather than only in the module.
        ("GET", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/readiness"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/probe"),
        ("POST", "/api/v1/prompts/{prompt_id}/revisions/{version_id}/case-drafts"),
        ("POST", "/api/v1/prompts/{prompt_id}/readiness/dismissals"),
        ("GET", "/api/v1/readiness/rules"),
        # prompt-improvement, INT-045..INT-050 (ADR-0068). Six operations, four
        # permissions, and NOTHING new minted — the action vocabulary stays at
        # twenty-seven. A module that reads every prompt in a workspace and
        # proposes edits to them sounds like one that should need its own action;
        # it does not, because every act here is one somebody could already
        # perform by hand.
        #
        # **`POST .../proposals/{id}/accept` writes no revision**, and is
        # nevertheless declared under `revision.create` rather than a read. It
        # hands back a candidate body destined for
        # `POST /api/v1/prompts/{prompt_id}/revisions`, and gating it lower than
        # the act it prefills would be a permission gap wearing a read's clothes.
        #
        # `/api/v1/prompts/{prompt_id}/findings` is the sixth module under that
        # shared prefix, and
        # `test_the_assembled_table_has_no_duplicate_operation` is still what
        # makes sharing it safe.
        ("GET", "/api/v1/improvement/findings"),
        ("GET", "/api/v1/prompts/{prompt_id}/findings"),
        ("POST", "/api/v1/improvement/findings/{finding_id}/dismiss"),
        ("POST", "/api/v1/improvement/proposals/{proposal_id}/accept"),
        ("POST", "/api/v1/improvement/proposals/{proposal_id}/dismiss"),
        # The read takes the SAME permission as the write, which is not the usual
        # split. The row states what the workspace has committed to spending every
        # week; somebody who cannot change that has no decision it informs, and a
        # read gated at `prompt.read` would publish the spending posture to every
        # prompt reader. It exists because the setting was write-only, so the
        # screen ADR-0068 asks for could not render its own toggle.
        ("GET", "/api/v1/workspaces/{workspace_id}/improvement-schedule"),
        ("PUT", "/api/v1/workspaces/{workspace_id}/improvement-schedule"),
        # INT-030 and D-39
        ("GET", "/healthz"),
        ("GET", "/readyz"),
        ("GET", "/metrics"),
    }
)

#: **The two versioned routes in Prope that declare no session**, and the set is
#: written as a literal so a third entry is an edit somebody has to make.
#:
#: ``POST /api/v1/auth/login`` is where a session comes from, so it cannot require
#: one. ``POST /api/v1/auth/register`` is where the *first* one comes from: A-071
#: forbids invitations and Prope has no outbound channel, so an install with no
#: accounts had no way to acquire one — `POST /api/v1/workspaces` authenticates,
#: and nothing could issue the session it wanted.
#:
#: Everything else under ``/api/v1`` declares ``require_session`` — a ``!=``
#: inside the loop below would have let the next unauthenticated route arrive as a
#: diff nobody reads.
SESSIONLESS_VERSIONED_ROUTES = frozenset(
    {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/register")}
)

#: Every module prefix that may appear in ``ManagementAction``. Three of the
#: eight so far; the remaining five add theirs as they mount.
ACTION_PREFIXES = (
    "call_ledger.",
    "access_control.",
    "provider_access.",
    "prompt_registry.",
    "prompt_search.",
    "prompt_conversion.",
    "prompt_ingestion.",
    "evaluation.",
    "release_control.",
    "chat_orchestrator.",
    "prompt_observation.",
    "prompt_readiness.",
    "prompt_improvement.",
    "agent_run.",
)

#: A-045: ``/healthz``, ``/readyz`` and ``/metrics`` are unversioned,
#: deliberately outside ``/api/v1``. INT-030 says the same in its own Version
#: column for the first two.
#:
#: **``/metrics`` joins them under the same rule for a different reason**, and
#: the difference is worth keeping visible: the health routes are unauthenticated
#: because an *operator* has no session, and ``/metrics`` is unauthenticated
#: because a *scraper* has none and never will — and because call-ledger has
#: nothing to authorise against (ADR-0018 forbids it an edge to access-control).
#:
#: This set is also **the exemption list for access-control's AC-10** — *"every
#: route in every module declares an action from the vocabulary; a route
#: declaring none fails the test rather than defaulting to unauthenticated"*.
#: Phase 3 grew it from two entries to three, and Phase 7/9 is what meets it.
#: Enlarging an exemption set is a decision, so it is recorded where the set is.
UNVERSIONED = frozenset({"/healthz", "/readyz", "/metrics"})

#: Field, property and parameter names that would mean the body store had grown a
#: read path. ``ledger.call_body``'s three columns are ``request_body``,
#: ``response_body`` and ``byte_size``; the rest are the names somebody would
#: reach for while adding one (ADR-0018, A-105, CL-10).
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "request_body",
        "response_body",
        "byte_size",
        "body",
        "bytes",
        "payload",
        "request_payload",
        "response_payload",
        "raw_body",
        "call_body",
    }
)

#: ``schema.field -> the written reason this one is not the body store's``.
#:
#: The list above was written when ``body`` had one meaning in Prope. It has two
#: from Phase 13: ``ledger.call_body`` holds the request and response of a LIVE
#: CALL, has no read path in the MVP, and is what ADR-0018 and A-105 are about —
#: and ``registry.revision.body`` holds the PROMPT TEXT, which the registry
#: exists to serve and whose read path is the product.
#:
#: The exemption is deliberately per **field**, not per module and not by
#: dropping ``body`` from the set: ``request_body``, ``response_body``,
#: ``raw_body``, ``call_body`` and ``byte_size`` remain unconditionally forbidden
#: everywhere, including in prompt-registry, so a registry model that grew one of
#: those still fails here.
SANCTIONED_BODY_FIELDS: dict[str, str] = {
    "RevisionCreate.body": (
        "the prompt body an author is saving (A-050 caps it at 32 KiB). This is the request that "
        "CREATES a revision, and a registry with no way to submit prompt text is not a registry. "
        "Nothing here reaches ledger.call_body, which prompt-registry may not read at all — "
        "call-ledger is a sink and that read path is gated by OQ-013."
    ),
    "RevisionRead.body": (
        "the prompt body on the revision DETAIL shape, which the review screen and the diff both "
        "render. Deliberately absent from RevisionSummaryRead, so the revision LIST does not carry "
        "twenty bodies to draw a column of dates — and absent from PromptRead entirely, along with "
        "search_text, which is the second copy T-017 keeps out of every response."
    ),
    "AdoptionProposalRead.body": (
        "the canonical body A-154 PROPOSES for an observed prompt, with its variable slots cut. It "
        "is the entire point of the adopt screen: a person compares it against what their product "
        "actually sent and posts it to prompt-registry's create routes, or does not. Withholding it "
        "would leave a route that returns a name and a slot count and asks somebody to accept a body "
        "they cannot see. Not a ledger body — nothing in prompt-observation can read ledger.call_body, "
        "and the observed text lives in observation.observation, which has a redact route and a "
        "delete route from its first commit (SR-4) precisely because it holds customer text nobody "
        "submitted."
    ),
    "SightingRead.body": (
        "the drift view, and the only field in it that is ever populated — a sighting carries a body "
        "ONLY when it changed one, which is the rule that keeps observation.sighting from becoming "
        "ledger.call_body at the same volume on the readable side of ADR-0018. 'The body changed on "
        "Tuesday and nobody reviewed it' is the governance value that arrives before any migration, "
        "and it cannot be shown without showing what it changed to. NULL on every sighting of a "
        "redacted group, cleared by the same statement that redacts the parent."
    ),
}

APP_SOURCE = Path(prope.app.__file__).read_text(encoding="utf-8")

#: ``(path, the name mounted there)``, and the list is exactly one long.
#:
#: A ``Mount`` is invisible to :func:`prope.session_auth.assembled_routes` and to
#: ``app.openapi()``, so every route assertion in this repository is blind to
#: whatever is behind one. ADR-0050 spends that blindness deliberately and once:
#: the gateway is a separate ASGI application object because Starlette scopes
#: exception handlers per APPLICATION, and the OpenAI error contract must not be
#: a runtime comparison against ``request.url.path`` inside a shared handler.
#: ``/v1`` is OpenAI's wire version and not ours to bump (INT-022).
#:
#: Anything else arriving here is the shape AC-10 exists to refuse.
SANCTIONED_MOUNTS = [("/v1", "gateway_app")]


def _table() -> set[tuple[str, str]]:
    """Every ``(method, path)`` the assembled application serves."""
    table: set[tuple[str, str]] = set()
    for route in assembled_routes(app):
        for method in route.methods:
            table.add((method, route.path))
    return table


def test_the_assembled_table_is_exactly_the_declared_routes() -> None:
    """Compared against a literal list. Both directions fail."""
    assert _table() == set(EXPECTED_ROUTES)


def test_the_openapi_schema_agrees_with_the_route_table() -> None:
    """The generated spec and the served table are the same set.

    INT-028's spec line is *"generated from FastAPI + pydantic v2 -> OpenAPI"*,
    so the schema is a real artifact rather than documentation — and a route
    excluded from the schema while still being served is exactly the shape a
    later reader would use to slip a ninth path past the list above.

    **This is also the assertion that fails the day somebody switches
    ``/metrics`` to ``application.mount(make_asgi_app())``.** A ``Mount`` appears
    in neither ``assembled_routes`` nor ``app.openapi()``, so the two walks would
    agree at seven and the count above would be the only thing to notice. Both
    halves are needed, which is why
    ``test_metrics_is_a_route_the_table_can_see_and_not_a_mount`` asserts them
    together rather than trusting either alone.
    """
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    assert documented == set(EXPECTED_ROUTES)


def test_every_versioned_route_declares_a_session_and_an_action() -> None:
    """AC-10's two-module form, and Pitfall 11's answer, over the real table.

    **Not vacuous**: the count is asserted first. ``include_router`` does not
    flatten routes into ``app.routes``, so a walk that missed them would iterate
    an empty set and pass.

    **The session half now carries two exemptions and the action half carries
    none.** ``POST /api/v1/auth/login`` is where a session comes from and
    ``POST /api/v1/auth/register`` is where the first one comes from; every
    versioned route still declares an action, including those two.
    """
    versioned = [route for route in assembled_routes(app) if route.path.startswith("/api/v1")]

    # INT-028's 5, INT-029's 18, INT-027's 10, INT-024's 11, INT-025's 9 and
    # INT-026's 11, across 4 + 15 + 6 + 8 + 7 + 10 paths. FOUR modules now mount
    # under `/api/v1/prompts/{prompt_id}` — access-control's grants,
    # prompt-registry's, evaluation's suites and runs, and release-control's
    # decision surface — and no module owns the prefix. INT-025's nine
    # operations sit on seven paths rather than nine because `/eval-suites`
    # takes GET and POST and `/eval-suites/{suite_id}` takes GET and PUT;
    # INT-026's eleven sit on ten because `/releases` takes GET and POST.
    #
    # INT-029 went from sixteen to eighteen when ADR-0052's SPA landed:
    # `GET /auth/session` and `POST /auth/register`, each on a path of its own.
    # OQ-134 already records that INT-029's own text and its lock file disagree
    # with an enumeration of the route list either one prints; these two are
    # counted here, where what is served is asserted.
    # INT-024 went from ten to eleven with ADR-0055's per-prompt call-record read.
    #
    # The four folder operations on `/folders` and `/folders/{slug}` are counted
    # separately from INT-024's eleven and are deliberately not folded into that
    # number: a folder is `prompt_property.namespace` with a display label, so it
    # mounts in prompt-registry, but no interface declares it and pretending
    # INT-024 says fifteen would make the spec look like it had grown on its own.
    #
    # Evaluation's nine dataset operations are counted separately from INT-025's
    # nine for the same reason. They sit on five paths — `/datasets` (GET and
    # POST), `/datasets/{dataset_id}` (GET, PUT and DELETE),
    # `/prompts/{prompt_id}/dataset-attachments` (GET and PUT),
    # `/prompts/{prompt_id}/datasets/draft`, and
    # `/prompts/{prompt_id}/eval-runs/from-attachments`. INT-025 does not
    # mention a dataset, because the interface predates the library existing.
    # **Two of the four routes added since this count was last written were the
    # playground's, and neither was listed above until step 6 walked the table**
    # — `POST /prompts/{id}/revisions/{version_id}/trials` and
    # `PUT /workspaces/{id}/keys/{key_id}/scope`. They are named where they
    # belong rather than absorbed into the totals, because the point of an
    # enumeration is that an unlisted route fails here.
    #
    # Step 6's prompt-detail tabs added the other two: INT-024 went to thirteen
    # with `GET /prompts/{id}/usage` beside the trial, and INT-025 to ten with
    # `GET /prompts/{id}/eval-runs`. That last one shares its path with the POST
    # that starts a run, which is why the operation count rises by two here and
    # the path count by one.
    # INT-029 went from nineteen to twenty-one with ADR-0056's lobby:
    # `GET /auth/workspaces` and `POST /auth/workspaces/{workspace_id}/enter`,
    # each on a path of its own. They are the two things a person may do while
    # their session names no workspace, and both declare `require_actor` rather
    # than `require_session` — which is a declared session boundary either way,
    # so the loop below is unchanged and the exemption set does not grow.
    #
    # INT-029 went from twenty-one to twenty-seven with ADR-0057's invitations:
    # three under `/workspaces/{id}/invites` (two of them sharing a path), two
    # decisions on `/members/{user_id}/approve` and `/reject`, and
    # `POST /auth/invites/redeem` — six operations on five new paths. The
    # redemption is the only one of the six a person can reach from the lobby, and
    # it declares `require_actor` for the same reason the two routes above do.
    #
    # INT-024 then went from thirteen to fifteen with the conversation chain:
    # `GET /prompts/{id}/conversations` and that path plus `/{conversation_id}`.
    # Two new paths, so the operation count and the path count rise together —
    # unlike the eval-runs pair, neither shares a path with an existing verb.
    # INT-029 then went from twenty-seven to THIRTY with ADR-0061's namespace
    # grants: list, create and revoke over `/namespaces/{namespace}/grants` and
    # that path plus `/{user_id}`. The same three operations `/prompts/{id}/grants`
    # already carries, one scope up.
    #
    # INT-035 is the eleventh interface to register routes and adds seven — six in
    # the lock's own list plus the redact route SR-4 asks for and the list had
    # folded into the DELETE.
    # 2026-08-20: the number moved from 114 to 121 and the sentence below was
    # RECOUNTED against the running table rather than incremented. Two of the
    # seven were already missing — chat-orchestrator had gained
    # `chat/messages/{id}/feedback` and `chat/pipeline` without this tally being
    # touched — which is exactly the drift a hand-maintained count is for, and it
    # went unnoticed because the assertion was failing for a different reason at
    # the same time. Counted per declared module prefix, so the next one to drift
    # names itself.
    # 80 until 2026-08-18. ADR-0061 adds two (`/namespaces/{namespace}/grants` and
    # that path plus `/{user_id}`) and INT-035 adds six — `/observations`,
    # `/observations/{id}` which carries both a GET and the DELETE, and four
    # sub-paths under it. Seven operations over six paths, because `redacted` and
    # `dismissed` and `adopted` and `proposal` each own one and the id path is
    # shared by two verbs.
    # 88 until 2026-08-20. ADR-0067 adds four paths, not five: the probe and the
    # case-drafts routes each own one under
    # `/prompts/{id}/revisions/{version_id}`, the dismissals route owns one, and
    # `/readiness/rules` owns the last — while `.../readiness` shares nothing and
    # is its own. The other three are chat-orchestrator's and evaluation's,
    # recounted with the operation total above.
    assert len(versioned) == 148, "including model-name reads, agent runs and call annotations"
    assert len({route.path for route in versioned}) == 119, "including model-name reads, agent runs and call annotations"

    for route in versioned:
        operations = {(method, route.path) for method in route.methods}
        if not operations & SESSIONLESS_VERSIONED_ROUTES:
            assert declares_session(route), route.path

        action = declared_action(route)
        assert action is not None, route.path
        assert action in MANAGEMENT_ACTIONS, action


def test_the_only_sessionless_versioned_route_is_the_one_that_issues_sessions() -> None:
    """The exemption set is not merely declared — it is the whole of what is exempt."""
    actual = {
        (method, route.path)
        for route in assembled_routes(app)
        if route.path.startswith("/api/v1") and not declares_session(route)
        for method in route.methods
    }

    assert actual == set(SESSIONLESS_VERSIONED_ROUTES)


def test_every_registered_action_is_declared_exactly_once() -> None:
    """One member per route, one route per member, no reuse.

    A copy-pasted route that kept its neighbour's action would declare a
    vocabulary member for a thing it does not do, and Phase 7's permission wiring
    would grant on that mistake. ``GET`` and ``POST`` on ``/api/v1/prices`` are
    separate routes with separate actions, which is why this counts operations
    rather than paths.
    """
    declared = []
    for route in assembled_routes(app):
        if not route.path.startswith("/api/v1"):
            continue
        action = declared_action(route)
        declared.extend([action] * len(route.methods))

    assert sorted(declared) == sorted(MANAGEMENT_ACTIONS)


def test_the_unversioned_routes_declare_no_session_and_no_action() -> None:
    """INT-030 and D-39: reachable by a caller who holds no session, by design.

    A health check behind an authentication boundary is a health check the
    compose healthcheck cannot make, and the readiness answer would then depend
    on the module whose availability it is reporting. ``/metrics`` is here for
    the neighbouring reason — a Prometheus scraper holds no session either — and
    the test is named for the property rather than for the health routes, because
    it now covers three paths and *"the health routes"* would have become a lie
    the day the third one arrived.
    """
    health = [route for route in assembled_routes(app) if route.path in UNVERSIONED]

    assert len(health) == len(UNVERSIONED)
    for route in health:
        assert not route.path.startswith("/api/v1")
        assert not declares_session(route), route.path
        assert declared_action(route) is None, route.path


def test_metrics_is_a_route_the_table_can_see_and_not_a_mount() -> None:
    """D-39 / Pitfall 7. The *shape* of the exposition surface, not just its path.

    ``application.mount("/metrics", make_asgi_app())`` is the documented way to
    serve a Prometheus registry from an ASGI application, and it is refused here.
    A ``Mount`` carries neither ``effective_route_contexts`` nor a ``dependant``,
    and :func:`prope.session_auth.assembled_routes` appends a route only if it
    has one of those two — so a mounted exposition is **served, unauthenticated,
    and absent from every route assertion in this repository**. Nothing else in
    the suite would notice: both count assertions above are built *from*
    ``assembled_routes``, and ``test_the_router_and_the_health_routes_are_the_
    only_things_mounted`` walks raw ``app.routes`` but asserts only that
    ``/docs``, ``/redoc`` and ``/openapi.json`` are absent. That is the same
    class of hole Broken Window #4 records, one layer out — a route the *helper*
    cannot see rather than one the *test* cannot see — and it is exactly the
    shape AC-10 exists to refuse.

    So this asserts the property rather than the path, in three directions:
    present in the table built from ``assembled_routes``, present in the OpenAPI
    schema, and **exactly one ``.mount(`` call in ``prope.app``**. The path alone
    would pass under a mount that happened to have a route beside it.

    **That one mount is ADR-0050's and it is named here rather than exempted by
    a weaker assertion.** Phase 19 makes the gateway a separate ASGI application
    object mounted at ``/v1``, because Starlette scopes exception handlers per
    APPLICATION and the OpenAI error contract cannot be a runtime comparison
    against ``request.url.path``. Its invisibility to ``assembled_routes`` is the
    point rather than an oversight: the gateway serves no ``ManagementAction``,
    declares no session, and answers in a shape ``EXPECTED_ROUTES`` above could
    not describe — so it is asserted against its own application object, under
    its own contract, in ``tests/architecture/test_gateway_route_table.py``.

    The set is written as a literal pair so a **second** mount is an edit
    somebody has to make here, with a reason, rather than a diff nobody reads.

    **An AST walk, not a string search**, for exactly the reason
    ``test_worker_imports_no_web_framework`` gives for its own: the docstrings in
    ``prope.app`` name ``app.mount(make_asgi_app())`` on purpose, at two places,
    so a reader meets the refused shape where the decision is explained. A grep
    would fail on the explanation. The walk asks the only question that matters —
    does this module *call* ``.mount`` on anything?

    The source it parses is ``APP_SOURCE``, this module's own constant declared
    above. ``prope.app`` declares no such name and must not gain one: a
    module-level ``read_text`` of its own source, in a production module, for a
    test's benefit, would be the first such thing in ``src/`` and is precisely
    what D-13's composition rules exist to refuse.

    The runtime half is the belt beside it. ``app.routes`` is walked for a
    ``starlette.routing.Mount`` instance — which catches a mount that arrived
    through any spelling at all, including one this file's parser never sees.
    """
    import starlette.routing

    assert ("GET", "/metrics") in _table()
    assert "/metrics" in app.openapi()["paths"]

    mounted = [
        node
        for node in ast.walk(ast.parse(APP_SOURCE, filename=prope.app.__file__))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mount"
    ]
    assert [
        (node.args[0].value, node.args[1].id) for node in mounted
    ] == SANCTIONED_MOUNTS, (
        "prope.app mounts something ADR-0050 did not sanction; a Mount is invisible to "
        "assembled_routes and therefore to every route assertion in this repository"
    )

    assert [
        route.path for route in app.routes if isinstance(route, starlette.routing.Mount)
    ] == [path for path, _ in SANCTIONED_MOUNTS]


async def test_metrics_answers_the_registry_without_a_session() -> None:
    """The behaviour, driven through the real ASGI stack.

    No cookie is sent, and the answer is ``200`` with the exposition rather than
    the ``401`` every ``/api/v1`` route gives — which is the whole point of the
    route sitting outside the versioned prefix.

    The content type is asserted as a **format claim**: ``generate_latest`` emits
    the 0.0.4 text format, and ``CONTENT_TYPE_LATEST`` in ``prometheus-client``
    0.26.0 says ``version=1.0.0``. Pinning the string here is what stops the
    constant being "modernised" into a label the payload does not honour.
    """
    response = await call(app, "GET", "/metrics")

    assert response.status_code == 200, response.body
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    assert b"prope_call_ledger_enqueued_total" in response.body


async def test_metrics_exposes_a_metric_nothing_has_incremented() -> None:
    """D-40's whole argument, observable on the wire for the first time.

    ``prope_call_ledger_missing_version_id_total`` exists to stay at zero, and
    ``REGISTRY.get_sample_value`` answers ``None`` — not ``0.0`` — for a metric
    nothing has touched. A metric defined lazily is therefore indistinguishable
    from one that was never wired, and no alert can be written against a series
    that does not exist. Defining all eighteen at import is what makes the
    ``# HELP`` and ``# TYPE`` lines below appear on a process that has served no
    traffic at all.
    """
    body = (await call(app, "GET", "/metrics")).body.decode()

    assert "# HELP prope_call_ledger_missing_version_id_total" in body
    assert "# TYPE prope_call_ledger_missing_version_id_total counter" in body


def test_metrics_declares_no_session_and_no_management_action() -> None:
    """ADR-0018, at the route table rather than in prose.

    call-ledger performs no permission check by design — it has no outbound edge
    to access-control — so there is nothing for this route to authorise against,
    and declaring an action it could never resolve would be worse than declaring
    none. Asserted separately from the ``UNVERSIONED`` loop above so that a later
    edit narrowing that set cannot quietly stop covering this path.
    """
    metrics = [route for route in assembled_routes(app) if route.path == "/metrics"]

    assert len(metrics) == 1
    assert not declares_session(metrics[0])
    assert declared_action(metrics[0]) is None


def test_no_schema_property_or_parameter_exposes_a_stored_body() -> None:
    """ADR-0018 / A-105: the body store has no read path, asserted over the spec.

    Over the **assembled OpenAPI schema** rather than over the source, because
    the claim is about what the API exposes and a model can reach the API through
    a route nobody remembered to read.

    Two fields are exempt and both are declared in
    :data:`SANCTIONED_BODY_FIELDS` with the reason. ``body`` acquired a second
    meaning in Phase 13 and the two are not the same asset.
    """
    schema = app.openapi()

    offenders: list[str] = []
    for name, model in schema.get("components", {}).get("schemas", {}).items():
        for field in model.get("properties", {}):
            if f"{name}.{field}" in SANCTIONED_BODY_FIELDS:
                continue
            if field.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{name}.{field}")

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if parameter["name"].lower() in FORBIDDEN_FIELD_NAMES:
                    offenders.append(f"{method.upper()} {path} ?{parameter['name']}")

    assert offenders == []


def test_every_sanctioned_body_field_carries_a_reason_and_still_exists() -> None:
    """The exemption cannot be used blank, and it cannot outlive its field.

    The second half is what makes this more than a copy of ``GLOBAL_TABLES``'
    blank check: an exemption for a model that has been renamed or deleted is an
    entry nobody will notice is dead, and the next field that happens to take
    the old name inherits a hole somebody else argued for.
    """
    blank = [name for name, reason in SANCTIONED_BODY_FIELDS.items() if not reason.strip()]
    assert blank == [], f"sanctioned body fields with no written reason: {blank}"

    schemas = app.openapi().get("components", {}).get("schemas", {})
    stale = [
        name
        for name in SANCTIONED_BODY_FIELDS
        if name.split(".")[1] not in schemas.get(name.split(".")[0], {}).get("properties", {})
    ]
    assert stale == [], f"exemptions for fields that no longer exist: {stale}"


def test_the_application_is_composed_by_hand_and_not_discovered() -> None:
    """D-13. The list of mounted routers is the import block, and nothing else.

    Three things would break the property, so three things are refused: a
    dynamic import, a filename-based scan, and a call to ``__import__``. The
    positive half is asserted too — the router is imported by name and included —
    because a file that merely *lacks* ``importlib`` is not yet a file that
    composes explicitly.
    """
    tree = ast.parse(APP_SOURCE, filename=prope.app.__file__)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "importlib" not in imported
    assert "pkgutil" not in imported

    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "__import__" not in calls

    assert "from prope.call_ledger.api import router as call_ledger_router" in APP_SOURCE
    assert "application.include_router(call_ledger_router)" in APP_SOURCE
    assert "from prope.access_control.api import router as access_control_router" in APP_SOURCE
    assert "application.include_router(access_control_router)" in APP_SOURCE
    assert "from prope.provider_access.api import router as provider_access_router" in APP_SOURCE
    assert "application.include_router(provider_access_router)" in APP_SOURCE
    assert "from prope.prompt_registry.api import router as prompt_registry_router" in APP_SOURCE
    assert "application.include_router(prompt_registry_router)" in APP_SOURCE
    assert "from prope.evaluation.api import router as evaluation_router" in APP_SOURCE
    assert "application.include_router(evaluation_router)" in APP_SOURCE
    assert "from prope.release_control.api import router as release_control_router" in APP_SOURCE
    assert "application.include_router(release_control_router)" in APP_SOURCE
    assert "from prope.chat_orchestrator.api import router as chat_orchestrator_router" in APP_SOURCE
    assert "application.include_router(chat_orchestrator_router)" in APP_SOURCE
    assert (
        "from prope.prompt_observation.api import router as prompt_observation_router"
        in APP_SOURCE
    )
    assert "application.include_router(prompt_observation_router)" in APP_SOURCE


def test_both_processes_declare_the_topology_from_one_definition() -> None:
    """D-24, fully asserted for the first time: ``app`` and ``worker`` share it.

    Plan 02-03 could only assert half of this, because ``prope.app`` did not
    exist. Identity rather than a name match: two modules each holding their own
    ``declare_topology`` would satisfy a name check and could then drift, which
    is the exact failure D-24 makes structurally impossible by having one
    definition.
    """
    assert prope.app.declare_topology is prope.worker.declare_topology

    startup = inspect.getsource(prope.app._start_publisher)
    assert "declare_topology(channel)" in startup


def test_the_module_states_the_readiness_rule_and_the_loss_window_that_survives() -> None:
    """D-16 is written at the code, not only in a plan, and that is checked.

    Plan 02-03 established the posture (``test_the_module_names_both_taskgroup_
    traps_and_the_windows_constraint``): a reasoning obligation that is only
    reviewed is an obligation somebody deletes in a tidy-up. The readiness rule
    and the loss window it leaves open are the two most deletable paragraphs in
    this repository, because both read as commentary until the day they matter.

    **This assertion was kept and its subject changed, deliberately.** Plan 02-05
    asserted ``"records genuinely"`` — the Phase 2 sentence saying the fallback
    did not exist yet and records were lost. CL-01 made that sentence false, and a
    docstring that has stopped being true is worse than no docstring, so the
    string that must now be present is ``"A-139"``: the remaining loss window is
    what the paragraph is about, and only the closed form names it.
    """
    assert "degraded-and-counted" in APP_SOURCE
    assert "CL-01" in APP_SOURCE
    assert "metadata_dropped_total" in APP_SOURCE
    assert "A-139" in APP_SOURCE


def test_both_publisher_branches_are_supervised_jobs_and_neither_is_a_bare_task() -> None:
    """D-32, asserted over the source because it is a composition property.

    A publisher started as a bare ``asyncio.create_task`` ends silently when an
    exception escapes it: every later ``enqueue`` fills the handoff and then
    drops, with no crash, no restart, and nothing in ``/readyz`` — which is the
    database alone by decision. The fallback makes that reachable, because a
    fallback can raise where ``publish_record`` could not.

    Both branches are asserted, not only the healthy one: **a job made entirely
    of fallback calls is the one that needs the restart most.**

    The refused string is the exact bare-task composition, not the identifier —
    ``run_publisher`` still appears inside the publisher branch's job closure, and
    that is correct.
    """
    assert "asyncio.create_task(run_publisher(" not in APP_SOURCE

    startup = inspect.getsource(prope.app._start_publisher)
    # Counted on the job map rather than on the bare name: the docstring above
    # explains why ``supervise()`` cannot be awaited from a lifespan, and a
    # substring count would count that sentence.
    assert startup.count("supervise({JOB_") == 2, "both branches compose through supervise()"
    assert "JOB_CALL_RECORD_PUBLISHER: publisher_job" in startup
    assert "JOB_CALL_RECORD_FALLBACK: fallback_only_job" in startup
    assert "build_fallback_writer(application.state.sessionmaker)" in startup


def test_the_application_object_makefile_run_targets_exists() -> None:
    """``prope.app:app`` — the target ``Makefile`` has named since Phase 1."""
    makefile = (Path(prope.app.__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )

    assert "prope.app:app" in makefile
    assert isinstance(app, FastAPI)


def test_the_router_and_the_health_routes_are_the_only_things_mounted() -> None:
    """No ``/docs``, no ``/redoc``, no ``/openapi.json`` on the served table.

    FastAPI mounts all three by default. INT-028 says the spec is *generated*
    from the code, not that it is served, and three unauthenticated routes behind
    Caddy's single ingress would be three routes nobody decided to have — as well
    as three entries in a table asserted against a literal list.
    """
    served: set[str] = set()
    for route in app.routes:
        expand = getattr(route, "effective_route_contexts", None)
        if expand is not None:
            served.update(context.path for context in expand())
        else:
            served.add(getattr(route, "path", ""))

    assert "/docs" not in served
    assert "/redoc" not in served
    assert "/openapi.json" not in served


def test_the_assembled_table_holds_no_route_this_phase_did_not_declare() -> None:
    """A belt-and-braces count, in the shape Phase 23 will grow.

    Phase 23 replaces the literal set above with eight modules' worth of paths.
    Until then this is the assertion that a router mounted for a side effect —
    a metrics endpoint, a debug route, a second health check — cannot arrive
    unnoticed.

    **A metrics endpoint did arrive, and the response was to declare it.** Phase
    3 added ``GET /metrics`` to ``EXPECTED_ROUTES`` above, which is the only
    honest way past this assertion: the alternative — mounting it where the walk
    could not see it — is refused by
    ``test_metrics_is_a_route_the_table_can_see_and_not_a_mount``. This test was
    not weakened to accommodate it, and the sentence above is left standing on
    purpose, because the next arrival gets the same choice.
    """
    extra = _table() - set(EXPECTED_ROUTES)
    missing = set(EXPECTED_ROUTES) - _table()

    assert extra == set(), f"routes nobody declared: {sorted(extra)}"
    assert missing == set(), f"routes that stopped being served: {sorted(missing)}"


def test_declares_action_refuses_an_action_outside_the_vocabulary() -> None:
    """A-115's closure, enforced at import so a typo is a startup error.

    ``ManagementAction`` is closed and an unrecognised action is a deny rather
    than an error in INT-001 — because *"a typo that silently allows is the
    failure this closure exists to prevent"*. A route is built at module import,
    so refusing here means the process does not come up rather than coming up
    with a route Phase 7's wiring cannot resolve.
    """
    for outside in ("call_ledger.price.reed", "", None, object()):
        try:
            declares_action(outside)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError(f"{outside!r} was accepted into the closed vocabulary")


def test_the_action_vocabulary_is_a_str_enum_of_machine_codes() -> None:
    """Literal ASCII, dotted, and prefixed by the module that owns the route.

    ``domain.py``'s rule for statuses, applied to actions: a value that is
    stored, transmitted or compared is a fact and stays literal wherever it
    travels. The ``call_ledger.`` prefix is what lets seven more modules add
    members to one vocabulary without ``price.read`` colliding.
    """
    for action in MANAGEMENT_ACTIONS:
        assert isinstance(action, str)
        assert action.value.startswith(ACTION_PREFIXES), action
        assert action.value == action.value.lower()


def test_no_route_is_reachable_except_through_the_application() -> None:
    """Each router carries its prefix; nothing mounts one a second time.

    All twelve routers are included exactly once, so every path they serve
    appears once in the assembled table. A router included twice — under two
    prefixes, or by two modules — is prompt-registry's route-uniqueness rule
    broken in the way that is hardest to see, because both copies work.
    """
    paths = [route.path for route in assembled_routes(app) for _ in route.methods]

    assert len(paths) == len(EXPECTED_ROUTES)
    # Fourteen with conversion, ingestion, improvement, and persistent agent
    # runs composed explicitly. The gateway is still not one —
    # ADR-0050 mounts it as a separate ASGI application with its own exception
    # handlers, so it is neither counted here nor expected to be.
    assert APP_SOURCE.count("include_router") == 14


def test_the_assembled_table_has_no_duplicate_operation() -> None:
    """prompt-registry's route-uniqueness rule, as its own assertion.

    Four modules mount routes under ``/api/v1/prompts/{prompt_id}`` — all four
    are here now, release-control's decision surface last — and three under
    ``/api/v1/workspaces/{id}``. **No module owns either prefix.** The lock file asks for this in as many words: *"A CI
    test asserts the assembled route table contains no duplicate (method, path)
    pair."*

    It is deliberately **not** implied by
    :func:`test_the_assembled_table_is_exactly_the_declared_routes`, which
    compares two SETS and would therefore be blind to a table serving the same
    operation twice. The duplicate has to be counted as a LIST to be visible at
    all — which is the same distinction ADR-0050 drew one pass earlier when it
    established that this build does not rely on route-registration order for
    anything that matters. An un-asserted shared namespace is that reliance
    wearing a different hat.
    """
    operations = [
        (method, route.path) for route in assembled_routes(app) for method in route.methods
    ]

    duplicates = sorted(
        {operation for operation in operations if operations.count(operation) > 1}
    )

    assert duplicates == [], (
        f"two routes serve the same operation: {duplicates}. Whichever mounted second wins, "
        "silently, and both modules' tests pass."
    )
