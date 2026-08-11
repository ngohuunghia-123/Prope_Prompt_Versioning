import { Coins, Warning } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import { Notification } from '@/components/Notification';
import type { EvaluationRun, TestInput } from '@/features/evaluation/types';

interface ComparisonResultsProps { run: EvaluationRun; inputs: TestInput[]; }

export function ComparisonResults({ run, inputs }: ComparisonResultsProps) {
  const { t, i18n } = useTranslation();
  const metrics = [
    { id: 'tokens', icon: Warning, value: new Intl.NumberFormat(i18n.language).format(run.tokens.candidate), detail: run.tokens.delta === null ? t(`evaluation.metrics.unavailable.${run.deltaUnavailableReason ?? 'incompleteRun'}`) : t('evaluation.metrics.tokensDetail', { baseline: run.tokens.baseline, delta: run.tokens.delta }) },
    { id: 'cost', icon: Coins, value: new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'USD', minimumFractionDigits: 3 }).format(run.cost.candidate), detail: run.cost.delta === null ? t(`evaluation.metrics.unavailable.${run.deltaUnavailableReason ?? 'incompleteRun'}`) : t('evaluation.metrics.costDetail', { baseline: run.cost.baseline, delta: run.cost.delta }) },
  ] as const;
  return (
    <section aria-labelledby="comparison-results-title" className="space-y-5">
      <div><p className="text-overline font-semibold text-muted">{t('evaluation.results.eyebrow')}</p><h2 id="comparison-results-title" className="mt-2 text-heading-2 font-semibold text-ink">{t('evaluation.results.title')}</h2><p className="mt-1 text-body text-muted">{t('evaluation.results.description')}</p></div>
      {run.deltaUnavailableReason ? <Notification className="max-w-none" tone="info" title={t('evaluation.metrics.unavailableTitle')}>{t(`evaluation.metrics.unavailable.${run.deltaUnavailableReason}`)}</Notification> : null}
      <div className="grid gap-3 sm:grid-cols-2">{metrics.map(({ id, icon: Icon, value, detail }) => <article key={id} className="rounded-modal border border-border bg-surface p-4 shadow-panel"><Icon aria-hidden className="size-5 text-secondary" /><p className="mt-4 text-heading-2 font-semibold text-ink">{value}</p><p className="mt-1 text-caption text-muted">{detail}</p></article>)}</div>
      <div className="space-y-4">{run.results.map((result) => {
        const input = inputs.find((item) => item.id === result.inputId);
        return <article key={result.inputId} className="overflow-hidden rounded-panel border border-border bg-surface shadow-panel"><header className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4 sm:p-5"><div><p className="text-caption text-muted">{t('evaluation.results.testCase')}</p><h3 className="mt-1 text-heading-3 font-semibold">{input?.name ?? t('evaluation.results.unknownInput')}</h3><p className="mt-1 text-caption text-muted">{input ? t('evaluation.results.assertion', { type: t(`evaluation.inputs.assertions.${input.assertionType}`), expected: input.expected }) : null}</p></div><StatusBadge tone={result.outcome === 'pass' ? 'active' : 'error'}>{t(`evaluation.results.outcomes.${result.outcome}`)}</StatusBadge></header><div className="grid lg:grid-cols-2"><section className="border-b border-border p-4 lg:border-r lg:border-b-0 sm:p-5"><p className="text-overline font-semibold text-muted">{t('evaluation.results.baseline')}</p><p className="mt-3 text-body text-muted">{result.baselineOutput ?? t('evaluation.results.baselineUnavailable')}</p></section><section className="p-4 sm:p-5"><p className="text-overline font-semibold text-muted">{t('evaluation.results.candidate')}</p><p className="mt-3 text-body text-ink">{result.candidateOutput}</p></section></div></article>;
      })}</div>
    </section>
  );
}
