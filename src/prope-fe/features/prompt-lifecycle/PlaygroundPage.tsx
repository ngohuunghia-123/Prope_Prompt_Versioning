import { ArrowRight, Flask, Play } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { promptOptions, playgroundOptions, useRunPlaygroundMutation, useRunEvalMutation } from '@/features/prompt-lifecycle/queries';
import type { PlaygroundRun, PromptDetail } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { HelpIcon } from '@/components/ui/HelpIcon';

function OutputPanel({ label, run, aria }: { label: string; run: PlaygroundRun; aria: string }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <Card title={label}>
      <pre aria-label={aria} className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-subtle p-4 font-mono text-caption text-ink">{run.outputA}</pre>
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricTile label={t('lifecycle.playground.tokens')} value={format.number(run.tokensA)} />
        <MetricTile label={t('lifecycle.playground.cost')} value={format.currency3(run.costA)} />
        <MetricTile label={t('lifecycle.playground.score')} value={format.score(run.scoreA)} />
      </div>
    </Card>
  );
}

function DraftOutputPanel({ label, run, aria }: { label: string; run: PlaygroundRun; aria: string }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <Card title={label}>
      <pre aria-label={aria} className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-subtle p-4 font-mono text-caption text-ink">{run.outputB}</pre>
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricTile label={t('lifecycle.playground.tokens')} value={format.number(run.tokensB)} />
        <MetricTile label={t('lifecycle.playground.cost')} value={format.currency3(run.costB)} />
        <MetricTile label={t('lifecycle.playground.score')} value={format.score(run.scoreB)} />
      </div>
    </Card>
  );
}

export function PlaygroundPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { promptId } = useParams();
  const resolvedPromptId = promptId ?? 'checkout-assistant';
  const promptQuery = useQuery(promptOptions(resolvedPromptId));
  const playgroundQuery = useQuery(playgroundOptions(resolvedPromptId));
  const runMutation = useRunPlaygroundMutation(resolvedPromptId);
  const runEval = useRunEvalMutation(resolvedPromptId);
  const [input, setInput] = useState('');
  const [context, setContext] = useState('');
  const [runError, setRunError] = useState<string | null>(null);
  const prompt: PromptDetail | undefined = promptQuery.data;
  const runs = playgroundQuery.data;
  const latest = runs?.[0];

  const productionRevision = prompt?.revisions.find((r) => r.status === 'inUse') ?? prompt?.revisions[0];
  const draftRevision = prompt?.revisions.find((r) => r.status === 'draft') ?? prompt?.revisions[1];
  const [selectedRevisionA, setSelectedRevisionA] = useState(productionRevision?.id ?? '');
  const [selectedRevisionB, setSelectedRevisionB] = useState(draftRevision?.id ?? '');

  const handleRunAgain = () => {
    setRunError(null);
    runMutation.mutate(
      { text: input.trim() || latest?.input || t('lifecycle.playground.inputPlaceholder'), revisionIdA: selectedRevisionA, revisionIdB: selectedRevisionB },
      { onError: () => setRunError(t('lifecycle.states.error.description')) },
    );
  };

  const handleRunEval = () => {
    runEval.mutate(undefined, {
      onSuccess: () => void navigate(`/app/prompts/${resolvedPromptId}/eval`),
    });
  };

  if (promptQuery.isPending || playgroundQuery.isPending) return <QueryState state="loading" />;
  if (promptQuery.isError) return <QueryState state="error" onRetry={() => void promptQuery.refetch()} />;
  if (!prompt || !latest) {
    if (playgroundQuery.isError) return <QueryState state="error" onRetry={() => void playgroundQuery.refetch()} />;
    return <QueryState state="empty" titleOverride={t('lifecycle.states.empty.title')} descriptionOverride={t('lifecycle.playground.noRuns')} />;
  }
  const revisionOptions = prompt.revisions.map((r) => ({ value: r.id, label: r.number }));
  const selectedRevA = prompt.revisions.find((r) => r.id === selectedRevisionA);
  const selectedRevB = prompt.revisions.find((r) => r.id === selectedRevisionB);
  const productionLabel = selectedRevA ? t('lifecycle.playground.revisionProduction', { revision: selectedRevA.number }) : t('lifecycle.playground.revisionProduction', { revision: '?' });
  const draftLabel = selectedRevB ? t('lifecycle.playground.revisionDraft', { revision: selectedRevB.number }) : t('lifecycle.playground.revisionDraft', { revision: '?' });

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.playground.eyebrow')}
        title={`${prompt.title} · Playground`}
        description={t('lifecycle.playground.description')}
      />
      {runError ? <Notification tone="error" title={t('lifecycle.states.error.title')}>{runError}</Notification> : null}
      <Card title={t('lifecycle.playground.selectRevision')}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex items-center gap-2">
            <label htmlFor="revision-select-a" className="text-caption font-medium text-ink">{t('lifecycle.playground.compareBaseline')}</label>
            <HelpIcon title={t('lifecycle.help.playground.versionSelector')}>
              <p>{t('lifecycle.help.playground.versionSelector')}</p>
            </HelpIcon>
            <select
              id="revision-select-a"
              value={selectedRevisionA}
              onChange={(e) => setSelectedRevisionA(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-body text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/25"
            >
              {revisionOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="revision-select-b" className="text-caption font-medium text-ink">{t('lifecycle.playground.selectRevision')}</label>
            <select
              id="revision-select-b"
              value={selectedRevisionB}
              onChange={(e) => setSelectedRevisionB(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-body text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus/25"
            >
              {revisionOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('lifecycle.playground.inputLabel')}>
          <div className="mb-1.5 flex items-center gap-1.5">
            <label htmlFor="playground-input" className="text-caption font-medium text-ink">{t('lifecycle.playground.inputLabel')}</label>
            <HelpIcon title={t('lifecycle.help.playground.input')}>
              <p>{t('lifecycle.help.playground.input')}</p>
            </HelpIcon>
          </div>
          <textarea
            id="playground-input"
            aria-label={t('lifecycle.playground.inputLabel')}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t('lifecycle.playground.inputPlaceholder')}
            rows={5}
            className="min-h-32 w-full resize-y rounded-lg border border-border bg-surface px-3 py-3 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
          />
        </Card>
        <Card title={t('lifecycle.playground.contextLabel')}>
          <textarea
            aria-label={t('lifecycle.playground.contextLabel')}
            value={context}
            onChange={(event) => setContext(event.target.value)}
            placeholder={t('lifecycle.playground.contextPlaceholder')}
            rows={5}
            className="min-h-32 w-full resize-y rounded-lg border border-border bg-surface px-3 py-3 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
          />
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <OutputPanel label={productionLabel} run={latest} aria={t('lifecycle.playground.revisionAria', { revision: selectedRevA?.number ?? '?' })} />
        <DraftOutputPanel label={draftLabel} run={latest} aria={t('lifecycle.playground.revisionAria', { revision: selectedRevB?.number ?? '?' })} />
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
        <Button type="button" intent="neutral" leadingIcon={<Flask aria-hidden className="size-4" />} loading={runMutation.isPending} onClick={handleRunAgain}>{t('lifecycle.playground.runAgain')}</Button>
        <Button type="button" intent="primary" leadingIcon={<Play aria-hidden className="size-4" />} loading={runEval.isPending} onClick={handleRunEval}>{t('lifecycle.playground.runEval')}</Button>
        <Button type="button" intent="ghost" trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => void navigate(`/app/prompts/${resolvedPromptId}`)}>{t('lifecycle.detail.historyTitle')}</Button>
      </div>
    </div>
  );
}
