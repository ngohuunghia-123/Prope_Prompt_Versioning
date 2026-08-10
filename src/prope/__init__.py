"""Prope — prompt registry and release-control system.

D-01: one installable `prope` package, each bounded context a subpackage
(`prope.call_ledger`, `prope.registry`, …), mirroring schema-per-module
one-to-one. There is no "frontend" or "backend" subpackage, because neither
owns a journey.
"""
