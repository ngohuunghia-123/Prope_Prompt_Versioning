# Verified UX/UI User Flow

## Scope and reading rule

This is a reconstruction of the executable application's interaction surface, not a proposed Prope product flow. Solid branches are supported by application code or tests. Dashed branches are explicitly **Unverified** product/design concepts: they appear in product/design documents but are unreachable from the running application because no corresponding frontend, endpoint, datastore, authentication, or authorization code exists.

```mermaid
flowchart TB
    %% Solid nodes/edges are verified runtime interaction evidence.
    %% Dashed nodes/edges are documented product/design concepts only; they are unreachable in this repository.

    subgraph Actors[Actors and roles]
        api_actor[Verified actor: anonymous API consumer]
        owner[Unverified product persona: Prompt Owner]
        reviewer[Unverified product persona: Reviewer / Approver]
        developer[Unverified product persona: Developer / AI Engineer]
    end

    subgraph Verified[Verified runtime interaction surface - no browser UI implemented]
        entry[Entry: an HTTP-capable client]
        auth{Authentication or role gate required?}
        action{Choose an available action}

        health[No page: health result]
        status[No page: agent-status result]

        chat_surface[Unverified client chat screen - no repository implementation]
        message{Message valid: 1 to 5000 characters?}
        validation_error[No page: validation error result]
        loading[Unverified loading state - client behavior is not implemented]
        processing{Unhandled processing failure?}
        chat_result[No page: response and analysis result]
        server_error[No page: server-error result]
        continue_chat{Send another message?}
        exit[Exit interaction]
    end

    api_actor -->|opens or calls service| entry
    entry --> auth
    auth -->|No credentials or roles are checked| action
    action -->|check health| health
    action -->|check agent status| status
    action -->|submit a chat message through a client| chat_surface
    chat_surface -->|enter and submit message| message
    message -->|No| validation_error
    message -->|Yes| loading
    loading -->|request is processed| processing
    processing -->|No| chat_result
    processing -->|Yes| server_error
    health -->|choose another action| action
    status -->|choose another action| action
    validation_error -->|correct message and resubmit| chat_surface
    chat_result --> continue_chat
    continue_chat -->|Yes| chat_surface
    continue_chat -->|No| exit
    server_error -->|retry behavior is unverified| chat_surface

    subgraph Absent[Verified absent or unimplemented browser UX]
        no_browser[No implemented browser route, page, layout, navigation, form, modal, or redirect]
        no_auth[No login, logout, identity, role selection, or authorization-denied screen]
        no_modal[No confirmation dialog or modal flow]
        no_empty[No implemented empty state]
    end

    entry -.->|repository scan establishes absence| no_browser
    auth -.->|therefore no alternate auth branch| no_auth
    chat_surface -.->|no implementation defines these states| no_modal
    chat_surface -.->|no implementation defines these states| no_empty

    subgraph DesignOnly[Documented Prope concepts - Unverified and unreachable from the executable application]
        owner_registry[Unverified screen: Prompt registry]
        owner_detail[Unverified screen: prompt detail and revision editing]
        owner_review[Unverified screen: submit revision for review]
        reviewer_queue[Unverified screen: review queue or decision card]
        reviewer_decision{Unverified decision: approve or request changes}
        developer_release[Unverified screen: release approved revision]
        developer_restore[Unverified screen: restore an approved revision]
    end

    owner -.->|design document describes ownership, revisions, and review| owner_registry
    owner_registry -.->|select prompt| owner_detail
    owner_detail -.->|submit for review| owner_review
    reviewer -.->|design document describes review role| reviewer_queue
    owner_review -.->|design-only handoff| reviewer_queue
    reviewer_queue -.->|make decision| reviewer_decision
    reviewer_decision -.->|approve - unverified| developer_release
    reviewer_decision -.->|request changes - unverified loop| owner_detail
    developer -.->|design document describes release and restore role| developer_release
    developer_release -.->|restore path - unverified| developer_restore

    no_browser -.->|makes every design-only screen unreachable at runtime| owner_registry
    no_browser -.->|makes every design-only screen unreachable at runtime| reviewer_queue
    no_browser -.->|makes every design-only screen unreachable at runtime| developer_release

    classDef verified fill:#eef7f5,stroke:#116466,color:#102a2b
    classDef decision fill:#fff7d6,stroke:#a76e00,color:#3d2a00
    classDef outcome fill:#f5f5f5,stroke:#555,color:#222
    classDef unverified fill:#fff,stroke:#8a8a8a,color:#595959,stroke-dasharray: 5 5

    class entry,health,status,chat_result verified
    class auth,action,message,processing,continue_chat decision
    class validation_error,server_error,exit outcome
    class owner,reviewer,developer,chat_surface,loading,no_browser,no_auth,no_modal,no_empty,owner_registry,owner_detail,owner_review,reviewer_queue,reviewer_decision,developer_release,developer_restore unverified
```

## Role and goal inventory

| Actor/role | Status | Verified goal or limitation |
|---|---|---|
| Anonymous API consumer | Verified | Call the public service to check health, check status, or submit a chat message. The code contains no identity or role check. |
| Prompt Owner | Unverified product persona | Product documentation says this persona should register, revise, control access to, and submit prompts for review. No implementation supports those actions. |
| Reviewer / Approver | Unverified product persona | Product documentation says this persona should inspect evidence and approve or request changes. No implementation supports it. |
| Developer / AI Engineer | Unverified product persona | Product documentation says this persona should retrieve, release, and restore approved revisions. No implementation supports it. |

## Verified interaction inventory for wireframing

| Entry/action | What the user can see or receive | Success / error / loop | UI-design status |
|---|---|---|---|
| Check service health | A JSON result with `status` and environment | Returns the status result; user can choose another action | No verified page or control |
| Check agent status | A static ready/agent JSON result | Returns the status result; user can choose another action | No verified page or control |
| Submit chat message | A response and analysis result if processing completes | Empty message is rejected with 422; unhandled processing error returns 500; a new message can be submitted | A client screen, loading affordance, error presentation, retry behavior, and success presentation are **Unverified** |

## Screen and state inventory

| Candidate screen/state | Status | Reason |
|---|---|---|
| Chat screen/form | Unverified | The API accepts a `message`, but no client source implements a page, input, button, navigation, or rendering. |
| Chat loading state | Unverified | The request is asynchronous in the service; no client state implementation exists. |
| Validation-error state | Unverified UI rendering | The service returns 422 for an empty message; how a client displays it is not defined. |
| Server-error state | Unverified UI rendering | The service converts unhandled exceptions to 500; how a client displays/retries is not defined. |
| Health/status pages | Unverified UI rendering | The service provides JSON endpoints only. |
| Login, logout, access-denied, role-selection pages | Not implemented | No identity/authentication/authorization code or UI files exist. |
| Empty state, confirmation dialog/modal, redirect | Not implemented | No frontend source defines these behaviors. |
| Prompt registry, prompt detail/editor, review queue/decision, release, restore | Unverified and unreachable | These are described by product/design documents, but are absent from the executable implementation. |

## Backend trace used only to verify visible outcomes

- `GET /health` returns `{ "status": "ok", "env": ... }`.
- `GET /api/v1/status` returns a static ready payload.
- `POST /api/v1/chat` requires a `message` of 1–5000 characters. It returns `response` and `analysis`, returns 422 when validation fails, and maps unhandled exceptions to 500.
- No state-changing operation exists: the current path does not persist a user, message, prompt, revision, review, or release.

## Evidence

- `src/main.py`
- `src/api/routes.py`
- `src/models/schemas.py`
- `tests/test_api/test_routes.py`
- `docs/codebase/STRUCTURE.md`
- `docs/codebase/ARCHITECTURE.md`
- `docs/prope_source_of_truth.md` (design/discovery-only personas and concepts)
- `DESIGN.md` (design-only workbench surface)
