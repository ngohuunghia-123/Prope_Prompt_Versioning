"""The broker seam: one topology definition, one connection shape.

ADR-0028 gives Prope exactly one work queue and its DLQ. This package holds the
declaration both processes call (D-24) and the connection lifecycle the
publisher runs on. It knows nothing about call records — ``call_ledger``
imports from here, never the other way round.
"""
