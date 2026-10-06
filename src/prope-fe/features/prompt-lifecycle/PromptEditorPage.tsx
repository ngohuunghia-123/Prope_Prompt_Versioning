import { useQuery } from '@tanstack/react-query';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from '@phosphor-icons/react';
import { Link, Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { NewPromptComposer } from '@/features/prompt-lifecycle/NewPromptComposer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReadinessPanel } from '@/features/prompt-lifecycle/components/ReadinessPanel';
import { promptOptions, routerCombosOptions } from '@/features/prompt-lifecycle/queries';
import { RouterComboSummary } from '@/features/prompt-lifecycle/components/RouterComboSummary';
import { latestVersionIsPublished, nextRevisionNumber } from '@/features/prompt-lifecycle/draftApi';
import type { RouterCombo } from '@/features/prompt-lifecycle/routerComboTypes';
import { AUTHORED_SOURCE, type PromptDetail, type PromptDraft, type PromptEditorValues, type Revision } from '@/features/prompt-lifecycle/types';
import type { ComposerDraftContext } from '@/features/prompt-lifecycle/useNewPromptComposer';
import { isValidSlug } from '@/lib/slugify';
import { internalReturnTo } from '@/features/prompt-lifecycle/lifecycleNavigation';

function getNewPromptValues(t: TFunction, namespace: string): PromptEditorValues {
  return {
    title: t('lifecycle.newPrompt.untitled'),
    // The folder decides the namespace; the name is folded from the title as it
    // is typed, so it starts empty rather than at a placeholder somebody has to
    // notice and clear.
    namespace,
    name: '',
    access: 'private',
    providerConfigId: '',
    upstreamModel: '',
    // `single` is the resting mode. The combo memory can switch it (ADR-0069),
    // and it does that from inside the binding fields rather than here, because
    // the switch has to survive a restored draft choosing otherwise.
    bindingMode: 'single',
    routeComboId: '',
    promptBody: t('lifecycle.newPrompt.defaultBody'),
    fallbackAnswer: t('lifecycle.newPrompt.defaultFallback'),
    changeSummary: t('lifecycle.newPrompt.defaultSummary'),
    tags: [],
    // Nothing imported yet. `sourceMode` is derived from here on — the Import
    // panel sets it by loading a source and clears it by removing one — so
    // `authored` is the resting state rather than a tab somebody chose.
    sourceMode: 'authored',
    sourceText: '',
    sourceFormat: 'txt',
  };
}

/**
 * Does this template still hold exactly the rungs the revision froze?
 *
 * Order included, because order IS the meaning. A combo whose second and third
 * rungs were swapped is a different route wearing the same name.
 */
function comboMatchesSnapshot(combo: RouterCombo | undefined, route: Revision['route']): boolean {
  if (!combo || combo.entries.length !== route.length) return false;
  return route.every((entry, index) => {
    const rung = combo.entries[index];
    return rung?.provider_config_id === entry.provider_config_id && rung.upstream_model === entry.upstream_model;
  });
}

function valuesFromPrompt(
  prompt: PromptDetail,
  combos: RouterCombo[],
  versionId?: string,
  changeSummary = '',
): PromptEditorValues {
  // Editing an existing revision is always the authored path: there is a body
  // already and nothing to import. The model name is split back apart for
  // display only — both halves are immutable here.
  const [namespace = '', name = ''] = prompt.modelName.split('/');
  const revision = prompt.revisions.find((candidate) => candidate.id === versionId) ?? prompt.revisions[0];
  const route = revision?.route ?? [];
  // ADR-0069. Preselect the source combo ONLY while it still holds exactly what
  // this revision froze. Preselecting it regardless would quietly re-bind the
  // prompt to whatever the template says NOW the moment somebody pressed save —
  // the precise surprise the snapshot decision exists to prevent — and dropping
  // to an empty pair instead would silently UNBIND it. So: combo mode with
  // nothing chosen, which the schema refuses until somebody chooses, beside a
  // notice saying why.
  const source = combos.find((candidate) => candidate.combo_id === revision?.routeComboId);
  const routed = route.length > 0;
  return {
    ...AUTHORED_SOURCE,
    title: prompt.title,
    namespace,
    name,
    access: prompt.access,
    providerConfigId: routed ? '' : revision?.providerConfigId || prompt.provider,
    upstreamModel: routed ? '' : revision?.upstreamModel || prompt.providerModel,
    bindingMode: routed ? 'combo' : 'single',
    routeComboId: routed && comboMatchesSnapshot(source, route) ? source?.combo_id ?? '' : '',
    promptBody: revision?.promptBody ?? prompt.promptBody,
    fallbackAnswer: prompt.fallbackAnswer,
    changeSummary,
    tags: revision?.tags ?? [],
  };
}

/**
 * The same shape, built from a version DRAFT instead of a saved revision. A
 * draft holds its parent's binding snapshot, so the combo-drift logic below is
 * the ADR-0069 rule again, one level up.
 */
function valuesFromDraft(draft: PromptDraft, prompt: PromptDetail, combos: RouterCombo[]): PromptEditorValues {
  const [namespace = '', name = ''] = prompt.modelName.split('/');
  const route = draft.route;
  const source = combos.find((candidate) => candidate.combo_id === draft.routeComboId);
  const routed = route.length > 0;
  return {
    ...AUTHORED_SOURCE,
    title: prompt.title,
    namespace,
    name,
    access: prompt.access,
    providerConfigId: routed ? '' : draft.providerConfigId || prompt.provider,
    upstreamModel: routed ? '' : draft.upstreamModel || prompt.providerModel,
    bindingMode: routed ? 'combo' : 'single',
    routeComboId: routed && comboMatchesSnapshot(source, route) ? source?.combo_id ?? '' : '',
    promptBody: draft.promptBody,
    fallbackAnswer: prompt.fallbackAnswer,
    changeSummary: '',
    tags: draft.tags,
  };
}

/**
 * The body an accepted improvement proposal handed over, or nothing.
 *
 * `ImprovementInboxPage` and `ImprovementTab` both navigate here with the
 * candidate in navigation state, because accepting a proposal records a
 * disposition and writes NO revision (SR-6) — the write is the person's own
 * second, explicit act, made here. Reading it is therefore not optional: the
 * accept has already spent the prompt's single open-proposal slot and written an
 * `improvement_proposal_accepted` event, so an editor that ignored the state
 * would leave a permanent record claiming a change that never arrived.
 *
 * Typed by hand and guarded, because `location.state` is `unknown` by
 * construction — anybody can navigate here with any state, including a browser
 * restoring a stale entry.
 */
function candidateBodyFrom(state: unknown): string | undefined {
  if (typeof state !== 'object' || state === null) return undefined;
  const value = (state as { candidateBody?: unknown }).candidateBody;
  return typeof value === 'string' && value.trim() ? value : undefined;
}

export function PromptEditorPage() {
  const { t } = useTranslation();
  const { promptId, folderId } = useParams();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const candidateBody = candidateBodyFrom(location.state);
  const returnTo = internalReturnTo(searchParams.get('returnTo'));
  const query = useQuery({ ...promptOptions(promptId ?? ''), enabled: Boolean(promptId) });
  // Read only to answer one question: does the template this revision was
  // frozen from still hold those exact rungs? Nothing on this page binds to a
  // combo — the composer does that — so a failed fetch degrades to "treat it as
  // drifted", which asks for a deliberate choice rather than making a silent one.
  const combosQuery = useQuery(routerCombosOptions);

  if (!promptId) {
    // A folder slug that the registry could never have issued cannot be a
    // namespace either, so there is nothing to compose against. Back to the grid
    // rather than a composer whose prefix would 422 on save.
    if (!folderId || !isValidSlug(folderId)) return <Navigate to="/app/prompts" replace />;
    // No promptId to pass: the import flow creates the prompt and routes to
    // whatever id the registry answered with.
    return <NewPromptComposer initialValues={getNewPromptValues(t, folderId)} />;
  }

  if (query.isPending) return <QueryState state="loading" loadingLayout="form" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (!query.data) return <QueryState state="empty" />;
  // The rail's own ordering: `revisions[0]` is the newest, and it is the one an
  // author is working from. A prompt always has at least one — the registry
  // creates a revision with the property — so this is a guard against a shape
  // change rather than an expected empty.
  const latestRevisionId = query.data.revisions[0]?.id;
  // Where a save lands is always the evaluation tab, and the composer builds
  // that destination itself — so what the editor passes along is only the
  // revision being edited, which the tab should open on. `focus` and
  // `returnTo` stay editor-local: they describe how the person got here (the
  // evaluation tab's add-provider handoff, an improvement acceptance), not
  // where a fresh revision should be read.
  const versionParam = searchParams.get('version');
  const evaluationParams = new URLSearchParams();
  if (versionParam) evaluationParams.set('version', versionParam);
  const focus = searchParams.get('focus');
  // The draft being edited, if any. Its id rides in the URL, so a refresh
  // reopens the same draft rather than silently starting a second one.
  const draftParam = searchParams.get('draft');
  const editingDraft = draftParam ? query.data.drafts.find((candidate) => candidate.id === draftParam) : undefined;
  if (editingDraft) evaluationParams.set('draft', editingDraft.id);
  // The add-provider handoff pre-fills the change summary, so a save made to
  // fix a binding records why the binding changed instead of leaving history
  // to guess.
  const guidedProviderBinding = focus === 'provider-binding';
  // ADR-0069's drift case. `editedRevision` is the one /edit opened against;
  // `driftedRoute` is true when it was routed and the template it came from no
  // longer holds those rungs — renamed rungs, a reordered list, or a combo
  // somebody deleted. All three read the same to the person: the choice has to
  // be made again, deliberately.
  const editedRevision = query.data.revisions.find((candidate) => candidate.id === versionParam)
    ?? query.data.revisions[0];
  const editorValues = editingDraft
    ? valuesFromDraft(editingDraft, query.data, combosQuery.data ?? [])
    : valuesFromPrompt(
      query.data,
      combosQuery.data ?? [],
      versionParam ?? undefined,
      guidedProviderBinding ? t('lifecycle.editor.providerBindingSummary') : '',
    );
  // The promote gate and the version number the draft would become are read
  // from the loaded history — which already includes any version an earlier
  // promotion created in this session.
  const draftContext: ComposerDraftContext | undefined = editingDraft ? {
    id: editingDraft.id,
    name: editingDraft.name,
    parentRevisionId: editingDraft.parentRevisionId,
    canPromote: latestVersionIsPublished(query.data.revisions),
    nextVersion: nextRevisionNumber(query.data.revisions),
    revisions: query.data.revisions,
    resolveBinding: (routeComboId: string) => {
      const combo = combosQuery.data?.find((candidate) => candidate.combo_id === routeComboId);
      return {
        route: combo?.entries ?? editingDraft.route,
        routeComboName: combo?.display_name ?? editingDraft.routeComboName,
      };
    },
  } : undefined;
  const driftedRoute = Boolean(editedRevision && editedRevision.route.length > 0)
    && editorValues.routeComboId === ''
    && !combosQuery.isPending;

  // The in-place edit: a Draft version of a prompt nothing of which is in use
  // is a working copy — saving overwrites it (same number) instead of minting
  // the next revision. Anything published, reviewed or approved keeps the
  // append-only flow; a reviewed improvement also needs its own revision so
  // its evaluation can be compared with the unchanged original.
  // The backend re-checks the status either way.
  const promptUnpublished = !query.data.revisions.some((revision) => revision.status === 'inUse');
  const inPlaceContext = !candidateBody && !editingDraft && promptUnpublished && editedRevision?.status === 'draft'
    ? { versionId: editedRevision.id }
    : undefined;

  return (
    <div className="grid gap-6">
      {/* The way back to wherever the editor was opened from — the evaluation
          tab's provider handoff, an improvement proposal. Saving has its own
          destination, so this link is for the person who opened the editor,
          read what they came to read, and found nothing to change; without it
          the only way back is the browser's, which is the one control the app
          cannot label. */}
      {returnTo ? (
        <Link
          to={returnTo}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
        >
          <ArrowLeft aria-hidden className="size-4" weight="bold" />
          {t('lifecycle.surface.backToOrigin')}
        </Link>
      ) : null}
      {/*
        The candidate from an accepted proposal, and the sentence that keeps the
        accept honest. The body is in the form and nothing is saved — the same
        claim the inbox made under its own button, repeated at the surface where
        it stops being true the moment somebody submits.
      */}
      {candidateBody ? (
        <Notification tone="info" title={t('improvement.proposal.prefillTitle')}>
          {t('improvement.proposal.prefillBody')}
        </Notification>
      ) : null}
      {/*
        The frozen route, shown read-only, because the composer's select cannot
        offer it: the template it came from is gone or has changed, and
        preselecting the CURRENT template would re-bind this prompt to rungs
        nobody approved. The revision below is untouched and keeps serving these
        exact rungs — what needs a new choice is the revision about to be
        written.
      */}
      {driftedRoute && editedRevision ? (
        <Notification tone="warning" title={t('lifecycle.editor.routeDriftTitle')}>
          <div className="grid gap-2">
            <p>
              {t('lifecycle.editor.routeDriftBody', {
                name: editedRevision.routeComboName || t('lifecycle.router.unnamedCombo'),
              })}
            </p>
            <RouterComboSummary entries={editedRevision.route} warnUnusable={false} />
          </div>
        </Notification>
      ) : null}
      <NewPromptComposer
        initialValues={{
          ...editorValues,
          ...(candidateBody ? { promptBody: candidateBody } : {}),
        }}
        mode="edit"
        targetPromptId={promptId}
        hasUnsavedSuggestion={Boolean(candidateBody)}
        evaluationSearch={evaluationParams.toString()}
        draftContext={draftContext}
        inPlaceContext={inPlaceContext}
      />
      {/*
        ADR-0067's card, against the LAST SAVED revision — not against the text
        in the form. There is no endpoint that scores an unsaved body, and
        inventing one would mean a rule firing on half a sentence somebody is
        still typing. So the panel follows saves, which is also the only moment
        the finding is about something that exists.

        The author declares the profile here (`canDeclare` defaults to true):
        this is the surface where "what is this prompt for?" is a question they
        are already answering, and a declaration silences a whole class of
        finding permanently rather than one at a time.

        A draft is recomputed on every read and never frozen, so editing and
        re-reading shows the card moving with the body.
      */}
      {latestRevisionId ? (
        <ReadinessPanel promptId={promptId} versionId={latestRevisionId} trigger="edit" canDeclare={false} />
      ) : null}
    </div>
  );
}
