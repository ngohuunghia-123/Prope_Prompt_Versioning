"""property-history — the audit trail, written inside its caller's transaction.

``dependencies: []``, ``outputs: []`` and — the only one in Prope —
``apis.consumes: []``. That last emptiness is what lets access-control depend on
this module without a cycle. ``workspace_id``, ``actor_id`` and ``target_id``
are values, not foreign keys (A-122), which is what makes ADR-0054's
tombstone-and-survive cost this module nothing; the only foreign key here points
at the module's own registry table.

**This module never opens a transaction**, where call-ledger's seams always do
(ADR-0023 against D-19). A refactor to a connection-per-call would destroy the
guarantee silently — see ``append.py``.

**Nothing here imports FastAPI, at any depth** (D-65, PH-07), so no route can be
mounted from this package even by accident.
"""
