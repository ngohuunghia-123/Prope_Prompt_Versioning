import { useQuery } from '@tanstack/react-query';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from '@phosphor-icons/react';
import { Link, Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { NewPromptComposer } from '@/features/prompt-lifecycle/NewPromptComposer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReadinessPanel } from '@/features/prompt-lifecycle/components/ReadinessPanel';
import { promptOptions } from '@/features/prompt-lifecycle/queries';
import { AUTHORED_SOURCE, type PromptDetail, type PromptEditorValues } from '@/features/prompt-lifecycle/types';
import { isValidSlug } from '@/lib/slugify';

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

function valuesFromPrompt(prompt: PromptDetail, versionId?: string): PromptEditorValues {
  // Editing an existing revision is always the authored path: there is a body
  // already and nothing to import. The model name is split back apart for
  // display only — both halves are immutable here.
  const [namespace = '', name = ''] = prompt.modelName.split('/');
  const revision = prompt.revisions.find((candidate) => candidate.id === versionId) ?? prompt.revisions[0];
  return { ...AUTHORED_SOURCE, title: prompt.title, namespace, name, access: prompt.access, providerConfigId: revision?.providerConfigId || prompt.provider, upstreamModel: revision?.upstreamModel || prompt.providerModel, promptBody: revision?.promptBody ?? prompt.promptBody, fallbackAnswer: prompt.fallbackAnswer, changeSummary: '', tags: revision?.tags ?? [] };
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
  const query = useQuery({ ...promptOptions(promptId ?? ''), enabled: Boolean(promptId) });

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
  // Only for somebody the evaluation step sent here. Saving already returns
  // them — the composer navigates to evaluation on every write — so this is the
  // other exit: the one for a person who opened the editor, read the binding,
  // and found nothing to change. Without it the only way back is the browser's,
  // which is the one control the app cannot label.
  const versionParam = searchParams.get('version');
  const returnToEvaluation =
    searchParams.get('from') === 'evaluation'
      ? `/app/prompts/${promptId}/evaluation/run${versionParam ? `?version=${encodeURIComponent(versionParam)}` : ''}`
      : undefined;

  return (
    <div className="grid gap-6">
      {returnToEvaluation ? (
        <Link
          to={returnToEvaluation}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg text-caption font-medium text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-focus"
        >
          <ArrowLeft aria-hidden className="size-4" weight="bold" />
          {t('lifecycle.registration.backToEvaluate')}
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
      <NewPromptComposer
        initialValues={{
          ...valuesFromPrompt(query.data, searchParams.get('version') ?? undefined),
          ...(candidateBody ? { promptBody: candidateBody } : {}),
        }}
        mode="edit"
        targetPromptId={promptId}
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
        <ReadinessPanel promptId={promptId} versionId={latestRevisionId} trigger="edit" />
      ) : null}
    </div>
  );
}
