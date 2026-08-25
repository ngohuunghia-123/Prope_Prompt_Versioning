"""This module's inbound seams. **One function, and it reads nothing decisive.**

This file did not exist until now, and its absence was not the same statement
that `prompt_improvement/seams.py` makes next door. That file is a leaf by
design and says so. This module is the opposite — it is read constantly, but it
was read the wrong way: `agent_run.lifecycle` held its own
`SELECT decision FROM release.approval`, which imports nothing, passes every
dependency test in the suite, and is still an undeclared edge into another
module's table. That is the hole `tests/architecture/test_no_cross_schema_sql.py`
exists to close.

**What is exported is a label, not a verdict.** `latest_decision` answers *"what
did a reviewer last say about this revision"* and returns the recorded word. It
does not answer *"may this be released"* — that question is
`release_control.commands`', it is asked at the moment of the write, and the
database constraint under it is what makes the answer binding (non-negotiable
2). A caller that treated `latest_decision(...) == "approved"` as permission
would be reading a stale row and would still be refused by the engine, which is
the arrangement working rather than a gap in it.

**Nothing here checks a permission**, for `prompt_registry.seams`' reason: the
caller has already read and authorised the prompt row it took the `prompt_id`
from (ADR-0020), and a second check here is a second answer that can disagree
with the first.
"""

from prope.release_control.domain import Decision, ReleaseKind, ReviewTaskStatus
from prope.release_control.repository import latest_decision

__all__ = [
    "Decision",
    "ReleaseKind",
    "ReviewTaskStatus",
    "latest_decision",
]
