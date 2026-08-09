# ADR-0047 — Dispatch connects to the address it validated, which is why the client is httpx

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: provider-access
**Related**: A-025, A-043, A-084, A-088, A-089, A-090, A-092, A-095, A-097, ADR-0013, ADR-0014,
ADR-0015, ADR-0017, ADR-0026, ADR-0033

## Context

`base_url` is a field on `provider_config`, editable from the dashboard, and the server then fetches it
**with the workspace's bearer token attached**. The lock names that for what it is — *"a server-side
request forgery primitive, and this one is editable from the dashboard"* — and promises a two-part
defence: a scheme allow-list plus resolved-address rejection for loopback, link-local and private
ranges, *"evaluated at save time and again at dispatch time — DNS answers change between those two
moments, and checking only the first is the standard way this defence fails."*

The promise is right and, as stated, incomplete. Re-resolving at dispatch time and then handing the
**hostname** to an HTTP client means the client resolves it again when it opens the connection. Nothing
binds the answer that was validated to the answer that is connected to; the window simply moves from
*between save and dispatch* to *between check and connect*. A resolver returning `203.0.113.10` to the
validation call and `169.254.169.254` a millisecond later defeats it, which is the documented shape of
this attack rather than an exotic one.

Closing it requires connecting to the address that was validated. That is a property of how the
connection is made, so it decides the client rather than following from it.

Three constraints already in this lock rule out the otherwise obvious choice — the `openai` Python SDK
— independently of the SSRF question:

- **A-088 / AC-7**: *"exactly one upstream request was issued — no retry occurs inside this module
  regardless of the error class."* The SDK retries twice by default.
- **ADR-0015 / AC-9**: *"an OpenAI-compatible provider that includes a field Prope does not model —
  then that field is present unchanged in what the caller receives."* The SDK parses into typed models,
  which drop unknown fields. It fails that criterion by design, not by configuration.
- **ADR-0017**: the classification table maps raw statuses, codes and transport conditions to
  `(class, origin, fallback_eligible, retryable)`. The SDK presents an exception hierarchy that would
  have to be unwrapped back into the statuses it was built to hide.

## Decision

**Dispatch uses `httpx` with a custom transport that connects to the address validated for that
dispatch, preserving the original hostname for TLS SNI and certificate verification.**

- Per dispatch: resolve `base_url`'s host, reject any answer in a loopback, link-local, private,
  multicast, or otherwise non-global range, then construct the transport bound to the surviving
  address. **The address validated is the address connected to**, so there is no second resolution to
  disagree with the first.
- **The hostname is preserved for SNI and for certificate verification.** Connecting to an IP with
  certificate checking relaxed would trade an SSRF hole for a TLS one; the certificate is still
  validated against the hostname the workspace configured.
- **Redirects are disabled.** A 302 is a resolution the guard never saw, and following one re-opens
  the hole from the other side. A provider that redirects its chat-completions endpoint fails
  verification (A-090) rather than being followed at dispatch time.
- Save-time validation is unchanged and still happens (A-090's probe uses the same transport, so the
  probe exercises the real path rather than an approximation of it).
- `httpx.Timeout` carries `connect` and `read` separately, so `deadline_ms` maps onto the phase that
  actually matters rather than one aggregate. **No retry is configured anywhere**, which satisfies
  A-088 by construction rather than by remembering to disable something.
- The response is handled as raw JSON and relayed as ADR-0015 requires — unknown fields pass through
  untouched because nothing ever parses them into a closed model.
- **The `openai` SDK remains a dependency, test-only.** AC-9's contract test asserts the returned object
  is valid by parsing it with the SDK's own model, which is exactly the use the lock already specified:
  *"not by hand-checking keys… a near-miss survives hand-built assertions and then breaks every
  consumer."* It is the right tool as an oracle and the wrong one as a client.

## Alternatives rejected

**The `openai` Python SDK for dispatch.** The natural fit for a module whose entire contract is the
OpenAI shape (ADR-0015), and it handles SSE framing and streaming for free — which is real work this
decision now owns. Rejected on the three constraints above, each of which is already an acceptance
criterion in this lock, and on the SSRF question decisively: the SDK owns its connection, so there is
nowhere to enforce a dispatch-time address check at all. Configuring `max_retries=0` addresses one of
the four objections.

**`httpx` re-validating by hostname only** — same client, same benefits, but the dispatch-time check
re-resolves and then lets the client resolve again on connect. Much simpler: no custom transport, no
SNI-versus-address handling, no interaction with redirects. Rejected because it is the save-time check
run twice. It catches a `base_url` whose DNS record was repointed permanently, and misses a resolver
answering differently between the check and the connect — which is the case the lock explicitly names as
*"the standard way this defence fails"*. Writing the defence and then implementing the version that
misses the named case is worse than not claiming it.

**`aiohttp`.** Mature, fast, good streaming, and it supports address pinning through its connector.
Rejected as a second HTTP stack: `httpx` arrives in the image regardless through FastAPI's test client,
and its per-phase timeout model maps onto `deadline_ms` more directly. Not a strong rejection — this one
is close, and it is recorded as close.

## Consequences

- **SSE parsing is now this module's code**, roughly thirty lines, and it is on the per-chunk 1 ms
  budget. It is unit-testable against recorded provider streams, which the SDK's internal parser was
  not, and ADR-0015's unknown-field pass-through is easier to guarantee at that level than through a
  typed model.
- **AC-11 must be restated.** It currently asserts a private-resolving `base_url` is refused *"when it
  is saved and again when it is dispatched"*. The replacement additionally asserts the connection went
  to the validated address — the meaningful version of the test is a resolver that answers differently
  on the second call, which is what proves the pinning rather than the checking. Recorded as owed to
  the step-6 sweep.
- Disabling redirects is a behavioural constraint on which providers can be registered. It is enforced
  at verification (A-090) so it surfaces on the dashboard rather than in production, consistent with
  how A-030's usage-object requirement is handled.
- The image carries one HTTP client for outbound calls and one SDK used only under test. That
  distinction has to survive dependency housekeeping, so `openai` belongs in the dev dependency group,
  not the runtime one.
- Nothing here changes what crosses the seam. ADR-0015 remains the dispatch contract and ADR-0017's
  classification is built from the raw statuses this client makes available — which it does more
  readily than the rejected option, so two decisions get easier rather than one.
