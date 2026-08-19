"""prompt-observation — the inventory of prompts nobody registered.

``dependencies: [access-control (hard), prompt-registry (soft)]``, and the edges
that matter run INTO it: the gateway calls INT-034 and this module never calls
back. It reads no other module's tables and writes no other module's rows —
adoption is a proposal a person carries to prompt-registry's own routes, which is
ADR-0060's shape and non-negotiable #1's guarantee restated (nothing here can put
a prompt into production, because nothing here can create one).

The module exists because of what integration actually costs: a team's prompts
live inside their code, and asking them to rewrite it before Prope is worth
anything is asking them to pay first and find out later. ADR-0059 lets a key
forward what it cannot resolve; this module turns that traffic into a list of the
prompts a workspace is really running, so *adopt this one* is a button rather
than a project.

**Not an observability product.** It counts PROMPTS and not requests, holds no
traces, no spans and no latency charts, and every screen ends in one action.
``positioning.md`` §2 refuses that category by name.

**Its lock is `ready_for_build: false` and this code respects that.** OQ-147 asks
whether the pilot may observe real production traffic at all, given A-020, and it
is unanswered. The switch is per-key, nullable, and off — a workspace that never
sets ``observe_namespace`` never reaches a line in this package.
"""
