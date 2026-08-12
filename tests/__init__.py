"""Prope's test suite.

Every test in this project runs against a real PostgreSQL 17 (D-02). The
unit/integration/security/architecture split here is about *scope* — one
function versus the whole write path — not about whether a database is present.
Mocking the driver would prove nothing about a policy, a privilege or a CHECK.
"""
