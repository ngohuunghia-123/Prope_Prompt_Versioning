import { ArrowLeft, Play, Sparkle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { evaluationOptions, useAddTestInput, useCreateSuite, useCreateSuiteVersion, useMarkEvidenceReady, useRunComparison } from '@/features/evaluation/api';
import { ComparisonResults } from '@/features/evaluation/components/ComparisonResults';
import { EvaluationState } from '@/features/evaluation/components/EvaluationState';
import { EvidenceReadiness } from '@/features/evaluation/components/EvidenceReadiness';
import { SuiteOverview } from '@/features/evaluation/components/SuiteOverview';
import { SuiteManager } from '@/features/evaluation/components/SuiteManager';
import { TestInputForm } from '@/features/evaluation/components/TestInputForm';
import { TestInputList } from '@/features/evaluation/components/TestInputList';
import type { EvaluationSuiteFormValues, TestInputFormValues } from '@/features/evaluation/types';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';

export function EvaluationEvidencePage() {
  const { id = '' } = useParams();
  const { t, i18n } = useTranslation();
  const workspace = useQuery(evaluationOptions(id));
  const addInput = useAddTestInput();
  const createSuite = useCreateSuite();
  const createVersion = useCreateSuiteVersion();
  const run = useRunComparison();
  const markReady = useMarkEvidenceReady();
  const primarySuiteId = `${id}-accuracy`;
  const [activeSuiteId, setActiveSuiteId] = useState(primarySuiteId);
  const activeSuite = workspace.data ? activeSuiteId === primarySuiteId ? { inputs: workspace.data.inputs, latestRun: workspace.data.latestRun } : workspace.data.additionalSuites.find((suite) => suite.id === activeSuiteId) : undefined;
  const allRuns = workspace.data ? [workspace.data.latestRun, ...workspace.data.additionalSuites.map((suite) => suite.latestRun)].filter((item) => item !== null) : [];
  const completedAt = allRuns.length ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(allRuns.map((item) => item.completedAt).sort().at(-1) ?? '')) : null;
  const addTestInput = async (values: TestInputFormValues) => {
    try { await addInput.mutateAsync({ promptId: id, suiteId: activeSuiteId, ...values }); return true; }
    catch { return false; }
  };
  const addSuite = async (values: EvaluationSuiteFormValues) => {
    try { const result = await createSuite.mutateAsync({ promptId: id, ...values }); const created = result.additionalSuites.at(-1); if (created) setActiveSuiteId(created.id); return true; }
    catch { return false; }
  };
  return (
    <PreservationShell activeId="registry" title={t('evaluation.pageTitle')} description={t('evaluation.pageDescription')}>
      <div className="mx-auto max-w-content space-y-5">
        <Link to={`/app/prompts/${id}/revisions`} className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('evaluation.actions.backToRevisions')}</Link>
        {workspace.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
        {workspace.isError ? <EvaluationState mode="error" onRetry={() => void workspace.refetch()} /> : null}
        {workspace.data ? <>
          <header className="overflow-hidden rounded-panel border border-border bg-surface shadow-floating">
            <div className="bg-hero p-5 text-inverse sm:p-8"><div className="flex flex-wrap items-center gap-2"><StatusBadge tone={workspace.data.readyForReview ? 'active' : 'pending'}>{workspace.data.readyForReview ? t('evaluation.status.ready') : t('evaluation.status.preparing')}</StatusBadge><span className="text-caption text-inverse/80">{t('revisions.version', { number: workspace.data.revisionNumber })}</span></div><div className="mt-6 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div className="max-w-copy"><p className="text-overline font-semibold text-inverse/70">{t('evaluation.hero.eyebrow')}</p><h1 className="mt-2 text-heading-1 font-semibold sm:text-display-2">{t('evaluation.hero.title')}</h1><p className="mt-3 text-body-large text-inverse/80">{workspace.data.revisionSummary}</p></div><div className="rounded-modal border border-inverse/20 bg-surface/10 p-4"><p className="text-caption text-inverse/70">{t('evaluation.hero.lastRun')}</p><p className="mt-1 text-body font-semibold">{completedAt ?? t('evaluation.hero.notRun')}</p></div></div></div>
          </header>
          <SuiteOverview workspace={workspace.data} activeSuiteId={activeSuiteId} versioning={createVersion.isPending} onSelect={setActiveSuiteId} onCreateVersion={(suiteId) => createVersion.mutate({ promptId: id, suiteId })} />
          <SuiteManager saving={createSuite.isPending} error={createSuite.isError} onCreate={addSuite} />
          <section aria-labelledby="test-inputs-title" className="rounded-panel border border-border bg-surface p-5 shadow-panel sm:p-7"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-overline font-semibold text-muted">{t('evaluation.inputs.eyebrow')}</p><h2 id="test-inputs-title" className="mt-2 text-heading-2 font-semibold">{t('evaluation.inputs.title')}</h2><p className="mt-1 text-body text-muted">{t('evaluation.inputs.description')}</p></div><span className="text-caption font-semibold text-muted">{t('evaluation.inputs.count', { count: activeSuite?.inputs.length ?? 0 })}</span></div><div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.7fr)]"><TestInputList inputs={activeSuite?.inputs ?? []} /><TestInputForm saving={addInput.isPending} onSubmit={addTestInput} /></div></section>
          {addInput.isError ? <Notification tone="error" title={t('evaluation.addFailed.title')}>{t('evaluation.addFailed.body')}</Notification> : null}
          <section className="rounded-panel border border-border bg-subtle p-5 shadow-panel sm:p-7"><div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><span className="grid size-11 shrink-0 place-items-center rounded-full bg-secondary text-inverse"><Sparkle aria-hidden className="size-6" weight="fill" /></span><div><h2 className="text-heading-2 font-semibold">{t('evaluation.run.title')}</h2><p className="mt-1 max-w-copy text-body text-muted">{t('evaluation.run.description')}</p></div></div><Button type="button" intent="secondary" loading={run.isPending} disabled={workspace.data.inputs.length === 0 && workspace.data.additionalSuites.every((suite) => suite.inputs.length === 0)} leadingIcon={<Play aria-hidden className="size-4" weight="fill" />} onClick={() => run.mutate(id)}>{allRuns.length ? t('evaluation.actions.runAgain') : t('evaluation.actions.run')}</Button></div></section>
          {run.isError ? <Notification tone="error" title={t('evaluation.runFailed.title')}>{t('evaluation.runFailed.body')}</Notification> : null}
          {activeSuite?.latestRun ? <ComparisonResults run={activeSuite.latestRun} inputs={activeSuite.inputs} /> : <EvaluationState mode="empty" />}
          <EvidenceReadiness workspace={workspace.data} markingReady={markReady.isPending} markError={markReady.isError} onMarkReady={() => markReady.mutate(id)} />
        </> : null}
      </div>
    </PreservationShell>
  );
}
