"""prompt-readiness — is this revision ready for the job it says it does?

ADR-0067. The answer is a MEASUREMENT and not an opinion: a shipped, versioned
library of adversarial cases, stratified by what the prompt declares about its
own exposure, run against the candidate revision. The card reports how many it
refused.

Three lanes, three meters:

* **Lane A** (``rules``) — static, deterministic, free, runs on every card.
* **Lane B** (``generation``, ``dspy_program``) — Prope's model, on request only,
  for the small closed set of findings no test can express.
* **Lane C** (``probe``) — the workspace's credential, behind ``probe.start`` and
  a spend ceiling. The measurement.

``profile`` is the file that makes this not a lint.
"""

__all__: list[str] = []
