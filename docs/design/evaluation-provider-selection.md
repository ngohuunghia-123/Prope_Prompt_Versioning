# Evaluation provider selection handoff

## Understanding summary

- Evaluation runs require the prompt revision to have a provider and model binding.
- The evaluation page currently opens a provider-registration form and asks for a new API key.
- Provider registration already belongs to the workspace provider-management surface.
- The prompt composer already loads registered provider configurations and their model catalogues.
- The evaluation warning should send the author back to that existing composer selection.
- Saving the composer creates a new immutable revision and returns to evaluation.
- No credential is read, copied, or changed by this flow.

## Assumptions

- Existing provider and model queries remain the source of truth.
- Workspace provider lists are small enough for the existing query and select components.
- Existing loading, empty, and catalogue-empty states in `ProviderBindingFields` remain authoritative.
- The selected revision is preserved in the navigation URL.
- The provider section is scrolled into view and its first select receives keyboard focus.

## Final design

Remove `ProviderRegisterDialog` and its evaluation-only binding mutation from `EvalRunPage`.
When the user activates “Add provider for workspace”, navigate to the prompt editor with the
current revision, `from=evaluation`, and `focus=provider-binding`. The prompt editor preserves
the existing return-to-evaluation behavior. `ProviderBindingFields` recognizes the focus target,
scrolls its section into view, focuses the provider select, and visually highlights the section.
The user then selects an existing provider and model and submits the composer; the normal save
flow creates a new revision and routes back to evaluation.

The focus treatment is intentionally transient: once provider data has settled, the field group
uses the compact control radius, scrolls into view, receives focus, and shows its highlight for
1.6 seconds before fading away. The query parameter remains in the URL so a deliberate reload can
replay the orientation cue without keeping a permanent border around editable fields.

## Error and edge-case behavior

- No registered providers: keep the existing empty hint and link to provider management.
- Provider catalogue loading or empty: keep the existing disabled model select and hint.
- Provider query error: expose a localized inline error and retry action in the shared field group.
- A revision already carrying a complete binding does not show the evaluation warning.
- Direct editor visits without `focus=provider-binding` behave exactly as before.

## Decision log

1. Chose navigation back to the composer over an inline evaluation selector to avoid duplicate
   provider/model state, validation, and revision-writing logic.
2. Removed provider registration from evaluation because credentials are workspace configuration,
   not evaluation-run input.
3. Used the existing query parameter pattern for a focus target so browser refreshes and return
   navigation retain the user's context.
4. Kept immutable revision creation in the existing composer submission path.
5. Chose a component-local 1.6-second highlight over removing the URL parameter. This preserves
   refresh and return navigation semantics while preventing the orientation cue from becoming
   persistent decoration.
6. Reduced the highlight radius from the modal token to the control token so the outline follows
   the two selects rather than reading as a nested card.
7. Step navigation must preserve the selected revision in both directions. The compose-to-evaluate
   link carries the current `version`; an actual save replaces that value with the newly created
   revision. Switching steps remains a read-only navigation action and never calls revision APIs.
8. On an evaluation-to-provider return, the frontend supplies a localized provider-binding summary
   as part of React Hook Form's `defaultValues`. It therefore satisfies the existing backend
   contract without marking the form dirty. Submitting an unchanged edit navigates to evaluation;
   only a dirty form enters the revision-write flow.

## Verification

- TypeScript typecheck, lint, and production build pass.
- Evaluation warning navigates to the correct revision's editor.
- Provider section is visible and focused on arrival.
- Saving a provider/model selection returns to evaluation with the new revision.
- No duplicate registration dialog remains on the evaluation page.
