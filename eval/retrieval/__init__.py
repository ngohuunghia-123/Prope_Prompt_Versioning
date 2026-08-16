"""Retrieval quality evaluation for the prompt-search module.

Everything here answers one question the unit and integration suites cannot:
**does search return the right prompt?** Those suites assert behaviour — a
private prompt stays hidden, an unindexed one is still reachable, a 503 is not
an empty list. None of them can fail when ranking gets worse, which is exactly
the failure this package exists to catch.

The design follows `docs/materials/7-ai-evaluation-benchmarking.pdf`: a golden
dataset with stratified difficulty levels and adversarial cases, metrics that
separate retrieval failure from ranking failure, and an LLM judge with an
explicit rubric for the pairs no human labelled.
"""
