"""prompt-registry — the record of every prompt property and its immutable revisions.

``dependencies: [access-control (hard), property-history (hard), provider-access
(soft)]``, and four forbidden edges that all run the other way: the gateway,
evaluation and release-control call this module and it never calls back, and
call-ledger is a sink (ADR-0018).

The module holds the two things the product's core value rests on. ``revision``
is every prompt body in Prope, append-only by privilege. ``prompt_property``
carries the released pointer — writable only through INT-013, and only ever at an
``Approved`` revision, refused by a database constraint rather than by code
(BR-03, ADR-0001).
"""
