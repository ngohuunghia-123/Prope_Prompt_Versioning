"""Access Control — the oracle six modules consult, and the one they can.

`docs/modules/access-control.lock.yml`. Authenticate every actor — a person with
a session, a consuming product with an API key — and answer every
may-this-actor-do-this question, so that **no other module holds a copy of the
rules**.

**`dependencies: [property-history]`, and nothing else, by construction rather
than by discipline.** Six modules call this one; it calls none of them. That is
not a rule this package obeys, it is a property of `may()`'s signature: deciding
whether somebody may edit a prompt needs the prompt's owner and access level,
which live in a table this module is forbidden to read — so **the caller passes
them in**, from the row it has already read (ADR-0020). The forbidden edge is
unnecessary rather than merely prohibited, and
`tests/architecture/test_access_control_depends_on_one_module.py` asserts it over
the import graph.

**Nothing here is cached, and no caller may cache an answer** (A-114, ADR-0022).
Every check reads current state, so revoking a key, removing a member or changing
a role is effective on the next request with no TTL to wait out and no cache to
invalidate. That is the property this module trades its read volume for, and it
is the sentence somebody needs to hear on the day a key ends up in a public
repository.

**Two secrets live here and they are hashed by two different primitives.** A
password is argon2id, deliberately slow, on no hot path. A consumer key is
SHA-256 over a 256-bit machine-generated secret, deliberately fast, on the
gateway's 5 ms budget. Anybody reading `passwords.py` beside `keys.py` will
assume one of them is a mistake, so ADR-0021 is cited on both.

**What this package must never grow.** A read of any subject it authorises
(ADR-0020); a cache of any answer (ADR-0022); a comparison of two actors'
identities (A-075 — self-approval is *recorded* by release-control, never
refused here); a negative or deny-override grant (A-111 — permissions add,
nothing subtracts); or a policy language (A-012).
"""
