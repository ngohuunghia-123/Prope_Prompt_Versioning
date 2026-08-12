"""Architecture tests — rules about the shape of the schema, not about a row.

These assert properties that hold across *every* table rather than facts about
one. ADR-0045 exists because the opposite framing — a rule stated per table —
selects for its own blind spot: the table nobody remembered is the table nobody
tested.
"""
