import {
  ArrowRight,
  CheckCircle,
  ClockCountdown,
  ListChecks,
  WarningCircle,
} from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import {
  summarizeEvaluationEvidence,
  type EvaluationEvidenceState,
} from '@/features/prompt-lifecycle/evaluationEvidence';
import {
  evalAttachmentsOptions,
  promptEvalRunsOptions,
} from '@/features/prompt-lifecycle/queries';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { cn } from '@/lib/cn';

interface PromptEvaluationPanelProps {
  promptId: string;
  revisionId: string;
}

const toneByState: Record<EvaluationEvidenceState, 'active' | 'pending' | 'error'> = {
  empty: 'pending', running: 'pending', stale: 'pending', attention: 'error', ready: 'active',
};

const surfaceByState: Record<EvaluationEvidenceState, string> = {
  empty: 'border-border bg-subtle',
  running: 'border-warning-strong bg-warning',
  stale: 'border-warning-strong bg-warning',
  attention: 'border-danger-strong bg-danger',
  ready: 'border-success-strong bg-success',
};

function iconFor(state: EvaluationEvidenceState) {
  if (state === 'ready') return <CheckCircle aria-hidden className="size-6" weight="fill" />;
  if (state === 'running') return <ClockCountdown aria-hidden className="size-6" weight="duotone" />;
  if (state === 'attention' || state === 'stale') return <WarningCircle aria-hidden className="size-6" weight="fill" />;
  return <ListChecks aria-hidden className="size-6" weight="duotone" />;
}

export function PromptEvaluationPanel({ promptId, revisionId }: PromptEvaluationPanelProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useInsightsFormat();
  const runs = useQuery(promptEvalRunsOptions(promptId, revisionId));
  const attachments = useQuery(evalAttachmentsOptions(promptId));
  const openEvaluation = () => void navigate(`/app/prompts/${promptId}/evaluation`);

  if (runs.isPending || attachments.isPending) {
    return (
      <section aria-labelledby="evaluation-evidence-title" className="border-y border-border p-4 sm:p-6">
        <h2 id="evaluation-evidence-title" className="font-display text-heading-3 text-ink">{t('lifecycle.insights.evaluation.observatory.title')}</h2>
        <ContentSkeleton label={t('common.loading')} layout="inline" className="mt-4" />
      </section>
    );
  }

  if (runs.isError || attachments.isError) {
    return (
      <section aria-labelledby="evaluation-evidence-title" className="border-y border-border p-4 sm:p-6">
        <h2 id="evaluation-evidence-title" className="font-display text-heading-3 text-ink">{t('lifecycle.insights.evaluation.observatory.title')}</h2>
        <div role="alert" className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-danger-strong bg-danger p-4">
          <p className="text-body text-danger-text">{t('lifecycle.insights.evaluation.observatory.error')}</p>
          <Button type="button" intent="neutral" size="small" onClick={() => { void runs.refetch(); void attachments.refetch(); }}>{t('common.tryAgain')}</Button>
        </div>
      </section>
    );
  }

  const summary = summarizeEvaluationEvidence(runs.data, attachments.data.some((item) => item.stale));
  const passRate = summary.cases === 0 ? '—' : format.percent(summary.passed / summary.cases);
  const cost = format.costs(summary.costs) ?? t('lifecycle.insights.unpriced');
  const stateKey = `lifecycle.insights.evaluation.observatory.states.${summary.state}`;

  return (
    <section aria-labelledby="evaluation-evidence-title" className="border-y border-border p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.insights.evaluation.observatory.eyebrow')}</p>
          <h2 id="evaluation-evidence-title" className="mt-1 font-display text-heading-3 text-ink">{t('lifecycle.insights.evaluation.observatory.title')}</h2>
          <p className="mt-1 max-w-2xl text-body text-muted">{t('lifecycle.insights.evaluation.observatory.description')}</p>
        </div>
        <StatusBadge tone={toneByState[summary.state]}>{t(`${stateKey}.label`)}</StatusBadge>
      </div>

      <div className={cn('mt-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4', surfaceByState[summary.state])}>
        <div className="flex min-w-0 items-start gap-3 text-ink">
          <span className="mt-0.5 shrink-0">{iconFor(summary.state)}</span>
          <div>
            <p className="font-display text-heading-3">{t(`${stateKey}.title`)}</p>
            <p className="mt-1 text-body text-muted">{t(`${stateKey}.detail`, { failed: summary.failed, errored: summary.errored })}</p>
            {summary.lastFinishedAt ? <p className="mt-1 text-caption text-muted">{t('lifecycle.insights.evaluation.observatory.lastRun', { when: format.dateTime(summary.lastFinishedAt) })}</p> : null}
          </div>
        </div>
        <Button type="button" size="small" trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={openEvaluation}>{t(`${stateKey}.action`)}</Button>
      </div>

      {summary.latestRuns.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile className="bg-transparent shadow-none" label={t('lifecycle.insights.evaluation.passRate')} value={passRate} />
          <MetricTile className="bg-transparent shadow-none" label={t('lifecycle.insights.evaluation.cases')} value={`${format.number(summary.passed)} / ${format.number(summary.cases)}`} detail={summary.failed + summary.errored > 0 ? t('lifecycle.insights.evaluation.failedAndErrored', { failed: summary.failed, errored: summary.errored }) : undefined} />
          <MetricTile className="bg-transparent shadow-none" label={t('lifecycle.insights.evaluation.observatory.coverage')} value={format.number(summary.latestRuns.length)} detail={t('lifecycle.insights.evaluation.acrossSuites', { count: summary.latestRuns.length })} />
          <MetricTile className="bg-transparent shadow-none" label={t('lifecycle.insights.evaluation.cost')} value={cost} detail={t('lifecycle.insights.evaluation.costDetail')} />
        </div>
      ) : null}
    </section>
  );
}
