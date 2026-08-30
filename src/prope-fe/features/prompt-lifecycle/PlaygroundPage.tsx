import { ArrowRight, CaretDown, SlidersHorizontal } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { BottomActionDock } from '@/components/BottomActionDock';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { PlaygroundChat } from '@/features/prompt-lifecycle/components/PlaygroundChat';
import { PlaygroundMeter } from '@/features/prompt-lifecycle/components/PlaygroundMeter';
import { PromptPickerDialog } from '@/features/prompt-lifecycle/components/PromptPickerDialog';
import { PlaygroundSettings } from '@/features/prompt-lifecycle/components/PlaygroundSettings';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { useTrialChat, type TrialSettings } from '@/features/prompt-lifecycle/components/useTrialChat';
import { promptOptions, promptsOptions } from '@/features/prompt-lifecycle/queries';
import { requiredVariables } from '@/features/prompt-lifecycle/trialApi';

const NO_SETTINGS: TrialSettings = { providerConfigId: '', upstreamModel: '', parameters: {} };

/**
 * The playground: talk to a revision, and watch what it costs.
 *
 * **Only the conversation lives here.** Credentials and the snippets that use
 * them are their own page (`/app/keys`), because they are a workspace's
 * integration surface and not part of trying a prompt — a person minting a key
 * for a second platform has no prompt in hand, and a person testing a draft has
 * no use for a key at all.
 *
 * **The chat cannot be reached with a key, and that is the design.** The gateway
 * serves released revisions only, enforced by a database constraint, because no
 * prompt reaches production without a recorded human approval. So a Draft has
 * exactly one door: the trial endpoint, behind a session and `run.start` rather
 * than behind a credential anybody could carry out of the building.
 *
 * **Which prompt is a query parameter, not a route.** The page is mounted both at
 * `/app/playground` (from the sidebar, prompt chosen here) and at
 * `/app/prompts/:promptId/playground` (step 5's flow, prompt already known), and
 * `?version=` carries the revision from the eval-run page. One component serves
 * both because the difference is where the id came from, not what the screen does.
 */
export function PlaygroundPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { promptId: routePromptId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const promptsQuery = useQuery(promptsOptions);

  const prompts = useMemo(() => promptsQuery.data ?? [], [promptsQuery.data]);
  const promptId = routePromptId ?? searchParams.get('prompt') ?? prompts[0]?.id ?? '';

  const promptQuery = useQuery({ ...promptOptions(promptId), enabled: promptId !== '' });

  const revisions = useMemo(() => promptQuery.data?.revisions ?? [], [promptQuery.data]);
  const [chosenVersion, setChosenVersion] = useState<string>();
  const versionId = chosenVersion ?? searchParams.get('version') ?? revisions[0]?.id ?? '';
  const revision = revisions.find((item) => item.id === versionId) ?? revisions[0];

  const [variables, setVariables] = useState<Record<string, string>>({});
  const [settings, setSettings] = useState<TrialSettings>(NO_SETTINGS);
  const [pickerOpen, setPickerOpen] = useState(false);

  const neededVariables = useMemo(
    () => requiredVariables(revision?.promptBody ?? ''),
    [revision?.promptBody],
  );
  const missingVariables = neededVariables.filter((name) => !(variables[name] ?? '').trim());

  const chat = useTrialChat({ promptId, versionId, variables, settings });

  function choosePrompt(next: string) {
    const params = new URLSearchParams(searchParams);
    params.set('prompt', next);
    params.delete('version');
    setChosenVersion(undefined);
    setVariables({});
    setSettings(NO_SETTINGS);
    chat.reset();
    // From the per-prompt route, switching prompts leaves that route rather than
    // rewriting its path — the URL would otherwise name one prompt and show
    // another.
    if (routePromptId) void navigate(`/app/playground?${params.toString()}`);
    else setSearchParams(params, { replace: true });
  }

  if (promptsQuery.isPending) return <QueryState state="loading" loadingLayout="form" />;
  if (promptsQuery.isError) {
    return <QueryState state="error" onRetry={() => void promptsQuery.refetch()} />;
  }

  const prompt = promptQuery.data;

  // The revision's own binding, or an override set on the settings panel. Either
  // one makes a turn possible; neither does not, and the composer says so rather
  // than inviting a send that returns the same configuration error every time.
  const bindable = Boolean(
    (settings.providerConfigId && settings.upstreamModel) ||
      (revision?.providerConfigId && revision.upstreamModel) ||
      (prompt?.provider && prompt.providerModel),
  );

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6 pb-24">
      <PageIntro
        eyebrow={t('lifecycle.playground.eyebrow')}
        title={prompt?.title ?? t('lifecycle.playground.workbenchTitle')}
        description={t(routePromptId ? 'lifecycle.playground.flowDescription' : 'lifecycle.playground.description')}
      />

      {!routePromptId && prompts.length > 0 ? (
        <>
          <button type="button" onClick={() => setPickerOpen(true)} className="flex w-auto max-w-full items-center justify-between gap-4 justify-self-start rounded-xl border border-border bg-surface p-4 text-left shadow-panel hover:border-focus focus-visible:outline-2 focus-visible:outline-focus">
            <span className="flex min-w-0 items-center gap-3"><span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-lg bg-info text-info-strong"><SlidersHorizontal className="size-5" weight="bold" /></span><span className="min-w-0"><span className="block text-caption font-medium text-muted">{t('lifecycle.playground.promptLabel')}</span><strong className="block truncate text-body text-ink">{prompt?.title ?? t('lifecycle.playground.workbenchTitle')}</strong></span></span>
            <span className="flex shrink-0 items-center gap-2 text-caption font-semibold text-secondary">{t('lifecycle.playground.picker.change')}<CaretDown className="size-4" weight="bold" /></span>
          </button>
          <PromptPickerDialog open={pickerOpen} prompts={prompts} selectedId={promptId} onClose={() => setPickerOpen(false)} onChoose={choosePrompt} />
        </>
      ) : null}

      {promptQuery.isPending ? (
        <QueryState state="loading" loadingLayout="form" />
      ) : promptQuery.isError ? (
        <QueryState state="error" onRetry={() => void promptQuery.refetch()} />
      ) : !prompt ? (
        <QueryState state="empty" />
      ) : (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <PlaygroundChat
            turns={chat.turns}
            streaming={chat.streaming}
            error={chat.error}
            bindable={bindable}
            missingVariables={missingVariables}
            configuration={
              <PlaygroundSettings
                revisions={revisions}
                versionId={versionId}
                onVersionChange={setChosenVersion}
                neededVariables={neededVariables}
                variables={variables}
                onVariableChange={(name, value) =>
                  setVariables((current) => ({ ...current, [name]: value }))
                }
                settings={settings}
                onSettingsChange={setSettings}
                promptTitle={prompt.title}
                lockRevision={Boolean(routePromptId)}
              />
            }
            onSubmit={chat.submit}
            onRetry={chat.retry}
            onReset={chat.reset}
          />
          <div className="grid content-start gap-4 xl:sticky xl:top-[calc(var(--prope-topbar-height)+1rem)]">
            <PlaygroundMeter
              usage={chat.lastUsage}
              totals={chat.totals}
              streaming={chat.streaming}
              received={chat.received}
            />
          </div>
        </div>
      )}

      {routePromptId ? (
        <BottomActionDock>
          <Button
            type="button"
            intent="ghost"
            onClick={() =>
              void navigate(
                `/app/prompts/${routePromptId}/evaluation/run?version=${encodeURIComponent(versionId)}`,
              )
            }
          >
            {t('lifecycle.playground.backToEval')}
          </Button>
          <Button
            type="button"
            trailingIcon={<ArrowRight aria-hidden weight="bold" className="size-4" />}
            onClick={() => void navigate(`/app/prompts/${routePromptId}`)}
          >
            {t('lifecycle.playground.continue')}
          </Button>
        </BottomActionDock>
      ) : null}
    </div>
  );
}
