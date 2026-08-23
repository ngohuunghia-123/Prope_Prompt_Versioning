"""prompt-improvement — is the released revision still doing the job it was approved to do?

ADR-0068. `prompt-readiness` asks the question before a release; nothing asked it
after one. A model does not crash when it degrades — it returns ``200 OK`` and
gets quietly worse, and every signal that it is doing so is already sitting in
``ledger.call_record``.

Two evidence sources, neither of which reads anybody's traffic content:

* **Detectors** (``detectors``) — arithmetic over call METADATA, through
  ADR-0055's one read path. Free, daily, no model decides whether an anomaly is
  real.
* **Re-probing** (``schedule``) — ``prompt-readiness``'s probe runner against the
  LIVE released revision on a cadence. Costs the workspace, weekly, opt-in.

And one control the whole module exists around: **``gate``**. A candidate edit
clears the prompt's own eval suite before any person sees it, or it is discarded
and counted and never rendered. A queue of unvalidated model-authored edits turns
the mandatory human approval into the rubber stamp it exists to prevent.

The model's job is narrow and stated in full: ``triage`` ranks anomaly clusters,
picks a remedy family from the set the anomaly already made reachable, and writes
one evidence sentence. It never decides whether an anomaly exists.
"""

__all__: list[str] = []
