# ADR-0059 — Call content has one controlled observability read path

**Status**: Accepted  
**Date**: 2026-08-20  
**Supersedes**: ADR-0018, A-105  
**Module boundary**: prompt-registry authorises; call-ledger only provides a tenant-scoped seam

## Decision

Stored request and response content may be read only through the prompt-scoped observability route.
The workspace must explicitly opt in (default off), the actor must be an Owner, Admin, or Reviewer,
the body must still be inside its retention window, and server-side redaction must succeed. Redaction
failure fails closed. Every successful content read appends an audit event that contains identifiers
but never content. The response is `private, no-store`.

Call metadata and telemetry-derived trace remain readable with `prompt.read`. The Trace tab does not
read a body: the client requests content only after the Request tab is opened. Viewer therefore sees
Content and Trace but never Request. There is no export, workspace-wide body search, raw-content
response, Langfuse integration, or observability explorer.

## Boundary and rationale

Call-ledger remains a sink and still makes no authorisation decision. Prompt-registry owns the route,
checks prompt visibility, workspace opt-in and role, and only then invokes the narrow tenant-scoped
body seam. This preserves the dependency direction behind ADR-0018 while deliberately replacing its
absolute “no reader” rule with an auditable least-privilege path.

## Consequences

- `GET /api/v1/prompts/{prompt_id}/call-records/{call_id}/observability` returns metadata-derived
  trace always and redacted messages only when `include_request=true` passes every gate.
- Retention expiry removes Request availability without breaking Content or Trace.
- Tests now assert the gates, redaction, audit and absence of raw content instead of asserting that no
  reader exists at all.

