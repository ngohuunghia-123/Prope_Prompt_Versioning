import { Clock, Info, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Tag } from '@/components/Tag';
import { WorkflowStatusIndicator } from '@/features/prompt-lifecycle/components/WorkflowStatusIndicator';
import type { WorkflowStep } from '@/features/prompt-lifecycle/types';
import { useElapsedSeconds } from '@/features/prompt-lifecycle/useElapsedSeconds';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

export interface WorkflowStepDetailProps { step: WorkflowStep; }

export function WorkflowStepDetail({ step }: WorkflowStepDetailProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const elapsed = useElapsedSeconds(step.startedAt, step.status === 'running');
  const duration = step.status === 'running' ? elapsed : step.durationSeconds;
  return (
    <section aria-labelledby="workflow-step-title" className="grid gap-4 animate-navigation-panel motion-reduce:animate-none">
      <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t(`lifecycle.workflow.stages.${step.stage}`)}</p><h3 id="workflow-step-title" className="mt-2 font-display text-heading-2 text-ink">{t(`lifecycle.workflow.steps.${step.id}.title`)}</h3><p className="mt-2 text-body text-muted">{t(`lifecycle.workflow.steps.${step.id}.description`)}</p></div><WorkflowStatusIndicator status={step.status} /></header>
      <dl className="grid gap-3 rounded-xl border border-border bg-subtle p-4 sm:grid-cols-3">
        <div><dt className="text-caption text-muted">{t('lifecycle.workflow.started')}</dt><dd className="mt-1 text-body font-medium text-ink">{step.startedAt ? format.date(step.startedAt) : t('lifecycle.workflow.noData')}</dd></div>
        <div><dt className="text-caption text-muted">{t('lifecycle.workflow.ended')}</dt><dd className="mt-1 text-body font-medium text-ink">{step.endedAt ? format.date(step.endedAt) : t('lifecycle.workflow.noData')}</dd></div>
        <div><dt className="text-caption text-muted">{t('lifecycle.workflow.duration')}</dt><dd className="mt-1 flex items-center gap-2 text-body font-medium text-ink"><Clock aria-hidden className="size-4" />{duration === undefined ? t('lifecycle.workflow.noData') : t('lifecycle.workflow.seconds', { count: duration })}</dd></div>
      </dl>
      {step.metrics?.length ? <div className="grid gap-3 sm:grid-cols-3">{step.metrics.map((metric) => <Card key={metric.label} className="min-h-0 p-4" title={metric.value}><p>{metric.label}</p></Card>)}</div> : null}
      {step.result ? <div className="flex gap-3 rounded-xl border border-info-strong bg-info p-4 text-body text-ink"><Info aria-hidden className="mt-0.5 size-5 shrink-0 text-info-strong" /><p>{step.result}</p></div> : null}
      {step.warning ? <div className="flex gap-3 rounded-xl border border-warning-strong bg-warning p-4 text-body text-ink"><WarningCircle aria-hidden className="mt-0.5 size-5 shrink-0 text-warning-strong" /><p>{step.warning}</p></div> : null}
      {!step.result && !step.warning && !step.metrics?.length ? <div className="rounded-xl border border-dashed border-border p-6 text-center text-body text-muted">{t('lifecycle.workflow.noData')}</div> : null}
      {step.branches.length ? <div><h4 className="text-caption font-semibold text-ink">{t('lifecycle.workflow.possibleBranches')}</h4><div className="mt-2 flex flex-wrap gap-2">{step.branches.map((branch) => <Tag key={branch} state="neutral">{t(`lifecycle.workflow.branches.${branch}`)}</Tag>)}</div></div> : null}
    </section>
  );
}
