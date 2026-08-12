"""INT-001…INT-005 — this module's public in-process surface.

Re-exports only. The implementations live in `permissions.py` (INT-001, 002, 004)
and `bootstrap.py` (INT-003, INT-005).

Transaction ownership differs per seam:

* `may` / `visible_subject_filter` take the **caller's** `AsyncSession`, already
  inside a `workspace_transaction`, so the answer comes from the same snapshot as
  the row the caller read.
* `authenticate_api_key` / `authenticate_session` take the **sessionmaker** and
  open their own, because they run before a tenant is known.

`may_resolve` takes a caller session: the gateway has already authenticated the
key and holds its workspace.
"""

from prope.access_control.bootstrap import (
    AuthenticatedKey,
    authenticate_api_key,
    authenticate_session,
    list_workspace_ids,
)
from prope.access_control.domain import (
    AccessLevel,
    Actor,
    ActorType,
    FilterMode,
    GrantLevel,
    Subject,
    SubjectType,
    VisibleFilter,
)
from prope.access_control.permissions import may, may_resolve, visible_subject_filter

__all__ = [
    "AccessLevel",
    "Actor",
    "ActorType",
    "AuthenticatedKey",
    "FilterMode",
    "GrantLevel",
    "Subject",
    "SubjectType",
    "VisibleFilter",
    "authenticate_api_key",
    "authenticate_session",
    "list_workspace_ids",
    "may",
    "may_resolve",
    "visible_subject_filter",
]
