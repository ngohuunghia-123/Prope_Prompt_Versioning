"""property-history — the audit trail, written inside its caller's transaction.

``dependencies: []``, ``outputs: []`` and — uniquely in Prope —
``apis.consumes: []``; that last emptiness is what lets access-control depend on
this module without a cycle.

**A startup step, never a surface.** Both composition roots import exactly
``load_action_registry`` and ``install_registry`` and nothing else: no router, no
FastAPI at any depth (D-65, ADR-0038). ``tests/architecture/test_history_
registry_is_installed_at_process_start.py`` asserts both halves.
"""
