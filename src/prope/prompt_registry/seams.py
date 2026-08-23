"""INT-009…INT-014 — this module's public in-process surface.

Re-exports only. The reads live in ``repository.py``, the diff in ``diff.py``,
and the three inbound commands in ``commands.py``.

**Every seam here takes the CALLER's ``AsyncSession``**, already inside a
``workspace_transaction``, and none of them opens one. For the two reads that is
so the answer comes from the same snapshot as the row the caller already read;
for the three commands it is load-bearing in a stronger way — release-control's
release row, its history append and the pointer write share one transaction, and
INT-013's *"there is no release without a trail"* is that sharing rather than a
convention.

**INT-036 is the seventh, added 2026-08-18 (ADR-0062).** ``list_namespaces``
answers *which namespaces does this workspace use*, and it is here rather than in
access-control for the reason ADR-0020 exists: the obvious home was ``may_resolve``,
which already takes the namespace as a parameter, and putting it there would have
made access-control read ``registry.folder``. This edge already runs the right way.

**Six seams, six failure semantics, and they are deliberately not uniform.**
INT-009 answers a typed miss rather than raising, because a model name that is
not released is an ordinary outcome on the gateway's hot path. INT-012 raises on
an illegal transition, INT-013 raises a conflict on the compare-and-set, and
INT-014 raises if nothing is released — because a withdrawal of nothing is a
caller bug rather than a no-op. They are registered as three separate seams for
exactly that reason: a caller must branch on which one it hit.

**Nothing here checks a permission.** Every consumer has checked INT-001 at its
own edge — the gateway through INT-003 and INT-004, evaluation and
release-control through ``may()`` — and a second check on the hot path is a
second thing that can disagree with the first.
"""

from prope.call_ledger.seams import PromptCallWindow
from prope.call_ledger.seams import summarise_prompt_calls as _summarise_prompt_calls
from prope.prompt_registry.commands import (
    clear_released_revision,
    set_released_revision,
    set_revision_status,
)
from prope.prompt_registry.diff import compute_diff as get_diff
from prope.prompt_registry.domain import (
    DiffResult,
    IllegalTransition,
    ModelName,
    ModelNameInvalid,
    NothingReleased,
    PromptRow,
    ReleasedListing,
    ReleasedPointerConflict,
    ResolveMiss,
    RevisionBinding,
    RevisionRead,
    RevisionStatus,
)
from prope.prompt_registry.repository import (
    list_namespaces,
    list_released,
    list_released_prompts,
    list_revisions,
    load_prompt,
    load_prompt_by_model_name,
    load_released_revision,
    load_revision,
    resolve,
)

#: INT-011 names the two reads ``get_revision`` and ``get_released_revision``;
#: the repository names them for what they do to a row. Bound here rather than
#: imported ``as``, so the seam name and the implementation name are both
#: greppable and neither is a rename of the other.
get_revision = load_revision

get_released_revision = load_released_revision

#: A WIDENING of INT-011, which registers two reads and a diff. It exists
#: because ADR-0020 makes a permission decision take the subject's ``owner_id``
#: and ``access_level`` **from the row the caller already read**, and
#: access-control may not read ``registry.prompt_property`` itself — so every
#: module that authorises an action against a prompt needs a way to read one.
#: This module's own routes call ``repository.load_prompt`` directly; evaluation
#: and release-control cannot, because reaching past a module's ``seams.py`` is
#: the thing the import allow-lists exist to refuse.
#:
#: The alternative was for evaluation to import ``prompt_registry.repository``,
#: which would make INT-011's registered surface a description of nothing. The
#: conflict between the registered three and the shipped four is raised as
#: ``OQ-145`` rather than resolved by editing ``interfaces.md``.
get_prompt = load_prompt

#: A SECOND widening of INT-011, and release-control is its only caller. The
#: review screen must diff a candidate against the revision that precedes it when
#: nothing is released, and the release screen must state how many revisions have
#: been created since an approval was recorded (``failure_modes``, the
#: approved-then-superseded scenario). Neither is answerable from
#: ``get_revision`` alone, and the alternative — importing
#: ``prompt_registry.repository`` — is the reach past this file that the import
#: allow-lists exist to refuse. Raised as ``OQ-146`` alongside ``get_prompt``'s
#: ``OQ-145`` rather than resolved by editing ``interfaces.md``.
list_revision_chain = list_revisions
get_prompt_by_model_name = load_prompt_by_model_name

#: **INT-043, added 2026-08-20 (ADR-0068).** One prompt's production traffic,
#: folded to counts over a window.
#:
#: **It lives here for ADR-0055's reason and not as a convenience.** The read
#: subject is call-ledger's table and the permission decision is registry's,
#: because call-ledger is a sink with no edge to access-control and therefore no
#: way to ask ``may()`` anything. ADR-0055 settled that the one read path out of
#: the sink runs *through this module, per prompt, behind* ``prompt.read``, and
#: this is that path with a window on it rather than a second path beside it.
#:
#: **prompt-improvement calls this and never ``prope.call_ledger``**, which its
#: own lock forbids by name: a direct edge would be the flat cross-prompt reader
#: ADR-0055 rejected, and it would disclose that private prompts exist through a
#: door nobody classified as a read (BR-01).
#:
#: Bound rather than imported ``as``, so both names stay greppable — the rule the
#: three re-exports above follow.
summarise_prompt_calls = _summarise_prompt_calls

__all__ = [
    "DiffResult",
    "IllegalTransition",
    "ModelName",
    "ModelNameInvalid",
    "NothingReleased",
    "PromptCallWindow",
    "PromptRow",
    "ReleasedListing",
    "ReleasedPointerConflict",
    "ResolveMiss",
    "RevisionBinding",
    "RevisionRead",
    "RevisionStatus",
    "clear_released_revision",
    "get_diff",
    "get_prompt",
    "get_released_revision",
    "get_revision",
    "list_namespaces",
    "list_released",
    "list_released_prompts",
    "list_revision_chain",
    "get_prompt_by_model_name",
    "resolve",
    "set_released_revision",
    "set_revision_status",
    "summarise_prompt_calls",
]
