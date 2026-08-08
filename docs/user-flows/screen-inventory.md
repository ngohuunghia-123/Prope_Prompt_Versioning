# Functional Screen Inventory

## Scope and status key

There are **no verified browser UI screens** in this repository. The records below follow [`overview.md`](overview.md): they preserve the only client-facing interaction supported by the runtime and separately record Prope workbench concepts that appear in product/design documentation. They are not a visual design specification.

- **Unverified client surface**: server behavior exists, but no screen/client code exists.
- **Unverified and unreachable**: documented product/design concept with no executable route, client, authentication, authorization, datastore, or supporting product endpoint.
- **Not implemented**: no repository evidence even describes a screen/flow beyond its absence.

## Screen inventory

### 1. Chat interaction

**Status:** Unverified client surface; not an implemented screen.

| Field | Inventory |
|---|---|
| User role | Verified: anonymous API consumer. No sign-in or role selection exists. |
| User goal | Submit one message and receive `response` and `analysis`. |
| Entry point | An HTTP-capable client invokes the public chat capability. A browser URL, route, or navigation entry is unverified. |
| Primary action | Enter and submit a message. |
| Secondary actions | Resubmit after validation failure; send another message after a response. A UI retry action after server failure is unverified. |
| Inputs | One required `message`; 1–5000 characters. |
| Information displayed | Unverified UI rendering of `response` and `analysis`. |
| Navigation destinations | No verified page navigation. The behavioral loop is submit → result → submit another message. |
| Empty state | Not implemented. No initial/conversation-empty presentation is defined. |
| Loading state | Unverified. The service performs asynchronous processing, but no client loading affordance exists. |
| Error state | Validation: 422 for an empty/invalid message. Processing: 500 for an unhandled exception. UI copy, placement, and retry behavior are unverified. |
| Success state | The client receives `response` and `analysis`; visual presentation is unverified. |
| Permission state | Public/anonymous at the code level: no authentication or authorization check is present. |
| Confirmation dialogs | Not implemented. |
| Repository evidence | `src/api/routes.py`; `src/models/schemas.py`; `tests/test_api/test_routes.py`; [`overview.md`](overview.md). |

### 2. Health-result presentation

**Status:** Unverified client surface; the runtime exposes a JSON result, not a page.

| Field | Inventory |
|---|---|
| User role | Verified: anonymous API consumer. |
| User goal | Check whether the service reports itself as healthy. |
| Entry point | An HTTP-capable client invokes the health capability. No browser route/page is implemented. |
| Primary action | Request the health result. |
| Secondary actions | Choose another available action. |
| Inputs | None. |
| Information displayed | A JSON result containing `status: "ok"` and `env`; any UI rendering is unverified. |
| Navigation destinations | No verified page navigation; conceptually returns to the action choice. |
| Empty state | Not implemented. |
| Loading state | Not implemented. |
| Error state | No explicit health-endpoint error behavior is specified in repository tests/code. |
| Success state | The JSON health result is returned. |
| Permission state | No authentication or authorization check is present. |
| Confirmation dialogs | Not implemented. |
| Repository evidence | `src/main.py`; `tests/test_api/test_routes.py`; [`overview.md`](overview.md). |

### 3. Agent-status-result presentation

**Status:** Unverified client surface; the runtime exposes a JSON result, not a page.

| Field | Inventory |
|---|---|
| User role | Verified: anonymous API consumer. |
| User goal | Check reported agent readiness. |
| Entry point | An HTTP-capable client invokes the agent-status capability. No browser route/page is implemented. |
| Primary action | Request the status result. |
| Secondary actions | Choose another available action. |
| Inputs | None. |
| Information displayed | A static ready status and agent name; any UI rendering is unverified. |
| Navigation destinations | No verified page navigation; conceptually returns to the action choice. |
| Empty state | Not implemented. |
| Loading state | Not implemented. |
| Error state | No explicit status-endpoint error behavior is specified in repository tests/code. |
| Success state | The static status result is returned. |
| Permission state | No authentication or authorization check is present. |
| Confirmation dialogs | Not implemented. |
| Repository evidence | `src/api/routes.py`; `tests/test_api/test_routes.py`; [`overview.md`](overview.md). |

### 4. Prompt registry

**Status:** Unverified and unreachable product/design concept.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Prompt Owner. Other viewer permissions are unverified. |
| User goal | Find and select prompt property from a trusted registry. |
| Entry point | Unverified. `DESIGN.md` calls the prompt registry the primary workbench surface, but no application route exists. |
| Primary action | Select a prompt to open its detail. |
| Secondary actions | Search/filter are suggested by the stated workspace hierarchy, but exact actions/controls are unverified. |
| Inputs | Unverified. A search control is mentioned in the design hierarchy; fields and filters are not defined in implementation. |
| Information displayed | Unverified. Design mentions metrics and a registry table; product documentation describes ownership, history, status, and trusted/use information. |
| Navigation destinations | Unverified prompt detail and revision editing. |
| Empty state | Unverified. Design allows empty-state treatment but specifies no registry-empty content or action. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified; selecting a prompt is the documented flow transition, not an implemented outcome. |
| Permission state | Unverified. Product documentation proposes access control, but no access model/enforcement is implemented. |
| Confirmation dialogs | Unverified. |
| Repository evidence | `DESIGN.md`; `docs/prope_source_of_truth.md` §§2, 4.1; [`overview.md`](overview.md); `docs/codebase/STRUCTURE.md`. |

### 5. Prompt detail and revision editing

**Status:** Unverified and unreachable product/design concept.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Prompt Owner. |
| User goal | View a prompt, preserve/revise it, and move a revision toward review. |
| Entry point | Unverified selection from the Prompt registry. |
| Primary action | Submit a revision for review. |
| Secondary actions | View prompt/revision information and make edits are described at a goal level only; exact actions are unverified. |
| Inputs | Unverified. Product documentation establishes revisions conceptually but supplies no implemented editor schema or field set. |
| Information displayed | Unverified. Product documentation calls for ownership, history, trusted revision, and use status, but no screen contract exists. |
| Navigation destinations | Unverified submission-for-review surface; an unverified request-changes loop returns here. |
| Empty state | Unverified. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified; the diagram’s next concept is review submission. |
| Permission state | Unverified. Product documentation says owners control access; no code declares ownership or edit permission. |
| Confirmation dialogs | Unverified. |
| Repository evidence | `docs/prope_source_of_truth.md` §§2, 4.1; [`overview.md`](overview.md); `docs/codebase/ARCHITECTURE.md`. |

### 6. Revision submission for review

**Status:** Unverified and unreachable product/design concept. It may be a separate screen, panel, or action in a future client; the repository does not decide which.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Prompt Owner. |
| User goal | Submit a changed revision to a reviewer. |
| Entry point | Unverified prompt detail/revision editing. |
| Primary action | Submit for review. |
| Secondary actions | Unverified. |
| Inputs | Unverified. Product documentation says a reviewer should see evidence, but no submission fields or validation rules are implemented. |
| Information displayed | Unverified. |
| Navigation destinations | Unverified review queue/decision card. |
| Empty state | Unverified. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified handoff to the review concept. |
| Permission state | Unverified. No product route or authorization check exists. |
| Confirmation dialogs | Unverified. |
| Repository evidence | `docs/prope_source_of_truth.md` §4.1; [`overview.md`](overview.md); `docs/codebase/STRUCTURE.md`. |

### 7. Review queue or decision card

**Status:** Unverified and unreachable product/design concept.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Reviewer / Approver. |
| User goal | Understand a revision’s owner, change, quality, impact, cost, and risk; then decide. |
| Entry point | Unverified direct reviewer entry or handoff from review submission. |
| Primary action | Approve or request changes. |
| Secondary actions | Inspect the documented evidence; exact controls are unverified. |
| Inputs | A decision is described; decision reason/comment fields are unverified. |
| Information displayed | Product documentation names owner, change, output quality, impact, cost, risk, evidence, and usage context; the exact data contract is unverified. |
| Navigation destinations | Unverified approved path to release; unverified request-changes loop to prompt detail/editing. |
| Empty state | Unverified. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified approved or request-changes decision outcome. |
| Permission state | Unverified. Product documentation identifies the reviewer role, but code implements no user/role check. |
| Confirmation dialogs | Unverified. |
| Repository evidence | `docs/prope_source_of_truth.md` §4.2; `DESIGN.md` (secondary review-and-approval detail); [`overview.md`](overview.md); `docs/codebase/ARCHITECTURE.md`. |

### 8. Release approved revision

**Status:** Unverified and unreachable product/design concept.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Developer / AI Engineer. |
| User goal | Release an approved revision safely and know what is running. |
| Entry point | Unverified approval decision or developer entry. |
| Primary action | Release an approved revision. |
| Secondary actions | Retrieve/pin a known version and inspect use are product goals; exact UI actions are unverified. |
| Inputs | Unverified. Product documentation refers to approved revisions and known versions, but no release form/schema exists. |
| Information displayed | Unverified. Product documentation calls for trusted/approved revision and production-use awareness. |
| Navigation destinations | Unverified restore approved revision. |
| Empty state | Unverified. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified release success; no release endpoint, persistence, or application state change exists. |
| Permission state | Unverified. Product documentation identifies a developer role; code implements no release permission. |
| Confirmation dialogs | Unverified. |
| Repository evidence | `docs/prope_source_of_truth.md` §§2, 4.3; [`overview.md`](overview.md); `docs/codebase/ARCHITECTURE.md`. |

### 9. Restore approved revision

**Status:** Unverified and unreachable product/design concept.

| Field | Inventory |
|---|---|
| User role | Unverified product persona: Developer / AI Engineer. |
| User goal | Restore a previous approved revision when something goes wrong. |
| Entry point | Unverified release flow. |
| Primary action | Restore an approved revision. |
| Secondary actions | Unverified. |
| Inputs | Unverified selected revision/version and any restore parameters. |
| Information displayed | Unverified. Product documentation establishes a restore need but no screen data contract. |
| Navigation destinations | Unverified; no post-restore page/state is implemented. |
| Empty state | Unverified. |
| Loading state | Unverified. |
| Error state | Unverified. |
| Success state | Unverified restore success; no release history or state mutation exists in code. |
| Permission state | Unverified. |
| Confirmation dialogs | Unverified. A confirmation should not be assumed from the operation’s significance. |
| Repository evidence | `docs/prope_source_of_truth.md` §§2, 4.3; [`overview.md`](overview.md); `docs/codebase/ARCHITECTURE.md`. |

## Explicitly absent screens and flows

The following are not screen records because no source implements or describes their functional content. They must not be added to wireframes as existing behavior:

| Absent item | Status | Evidence |
|---|---|---|
| Login, logout, identity, role selection, access denied | Not implemented | `src/main.py`, `src/api/routes.py`, `docs/codebase/ARCHITECTURE.md` |
| Browser routes, global layout, navigation, redirects | Not implemented | `docs/codebase/STRUCTURE.md`; repository scan |
| Confirmation dialogs/modals | Not implemented | [`overview.md`](overview.md); repository scan |
| Generic empty states | Not implemented | [`overview.md`](overview.md); repository scan |

## Evidence boundary

The executable source supports only public JSON interactions and no persistence. `docs/prope_source_of_truth.md` and `DESIGN.md` are used only to identify documented product concepts; they do not verify that any listed Prope screen, role, permission, modal, loading state, or navigation has been implemented.
