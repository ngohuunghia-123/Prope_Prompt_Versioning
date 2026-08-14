import { ArrowRight, ListChecks } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { evalRunOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { EvalRun } from '@/features/prompt-lifecycle/types';

function formatPercent(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 0 }).format(value);
}

interface PromptEvaluationPanelProps {
  promptId: string;
}

export function PromptEvaluationPanel({ promptId }: PromptEvaluationPanelProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const query = useQuery(evalRunOptions(promptId));

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const evalRun: EvalRun | undefined = query.data;

  if (!evalRun) {
    return (
      <Card title={t('lifecycle.overview.tabs.evaluation')}>
        <p className="text-body text-muted">{t('lifecycle.states.empty.description')}</p>
        <div className="mt-4">
          <Button
            type="button"
            intent="primary"
            leadingIcon={<ArrowRight aria-hidden className="size-4" />}
            onClick={() => void navigate(`/app/prompts/${promptId}/eval`)}
          >
            {t('lifecycle.detail.evalResult')}
          </Button>
        </div>
      </Card>
    );
  }

  const recommendationLabel =
    evalRun.recommendation === 'readyForReview'
      ? t('lifecycle.evalRun.readyForReview')
      : evalRun.recommendation === 'needsChanges'
        ? t('lifecycle.evalRun.needsChanges')
        : t('lifecycle.evalRun.blocked');

  const tone =
    evalRun.recommendation === 'readyForReview'
      ? 'border-success-strong bg-success'
      : evalRun.recommendation === 'needsChanges'
        ? 'border-warning-strong bg-warning'
        : 'border-danger-strong bg-danger';

  return (
    <div className="grid gap-4">
      <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 ${tone}`}>
        <div className="flex items-center gap-3">
          <ListChecks aria-hidden className="size-5 shrink-0" weight="bold" />
          <div>
            <p className="text-overline font-bold tracking-navigation-overline uppercase">{t('lifecycle.evalRun.recommendation')}</p>
            <p className="mt-1 font-display text-heading-3">{recommendationLabel}</p>
          </div>
        </div>
        <div className="text-caption text-muted">{format.date(evalRun.createdAt)}</div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label={t('lifecycle.evalRun.faithfulness')} value={formatPercent(evalRun.metrics.faithfulness)} />
        <MetricTile label={t('lifecycle.evalRun.relevance')} value={formatPercent(evalRun.metrics.relevance)} />
        <MetricTile label={t('lifecycle.evalRun.completeness')} value={formatPercent(evalRun.metrics.completeness)} />
        <MetricTile label={t('lifecycle.evalRun.format')} value={formatPercent(evalRun.metrics.format)} />
      </div>

      <Button
        type="button"
        intent="primary"
        trailingIcon={<ArrowRight aria-hidden className="size-4" />}
        onClick={() => void navigate(`/app/prompts/${promptId}/eval`)}
      >
        {t('lifecycle.detail.evalResult')}
      </Button>
    </div>
  );
}
