import { ArrowUUpLeft, ListChecks, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { MetricTile } from '@/features/prompt-lifecycle/components/MetricTile';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { callRecordsOptions, productionStatsOptions, promptsOptions, useRollbackMutation } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { HelpIcon } from '@/components/ui/HelpIcon';
import type { ProductionStats } from '@/features/prompt-lifecycle/types';

function TrafficBar({ percent }: { percent: number }) {
  const { t } = useTranslation();
  const clamped = Math.max(0, Math.min(100, Math.round(percent * 100)));
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-subtle">
          <div className="h-full rounded-full bg-secondary" style={{ width: `${clamped}%` }} aria-hidden />
        </div>
        <HelpIcon title={t('lifecycle.help.trafficSplit.title')}>
          <p>{t('lifecycle.help.trafficSplit.body')}</p>
        </HelpIcon>
      </div>
      <p className="text-caption text-muted">{t('lifecycle.productionView.trafficPercent', { value: clamped })}</p>
    </div>
  );
}

function TopErrorRow({ stats }: { stats: ProductionStats }) {
  const { t } = useTranslation();
  const rate = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 2 }).format(stats.topError.rate);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-subtle p-3">
      <div className="flex items-center gap-3">
        <WarningCircle aria-hidden className="size-5 shrink-0 text-warning-strong" />
        <div>
          <p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('lifecycle.productionView.topError')}</p>
          <p className="text-body text-ink">{stats.topError.label}</p>
        </div>
      </div>
      <p className="text-body font-medium text-warning-strong">{rate}</p>
    </div>
  );
}

function TracesList({ records }: { records: ReadonlyArray<{ id: string; promptTitle: string; versionId: string; consumer: string; timestamp: string; tokens: number; cost: number; outcome: 'success' | 'fallback' | 'error' }> }) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  return (
    <ul className="grid gap-2 text-left">
      {records.map((record) => (
        <li key={record.id} className="grid gap-1 rounded-lg border border-border bg-subtle p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-body font-semibold text-ink">{record.promptTitle}</p>
            <StatusBadge tone={record.outcome === 'success' ? 'active' : record.outcome === 'fallback' ? 'pending' : 'error'}>{t(`lifecycle.calls.outcomes.${record.outcome}`)}</StatusBadge>
          </div>
          <p className="text-caption text-muted">{record.consumer} · {format.date(record.timestamp)}</p>
          <p className="text-caption text-muted">{format.number(record.tokens)} tokens · {format.currency(record.cost)}</p>
        </li>
      ))}
    </ul>
  );
}

export function ProductionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { promptId } = useParams();
  const resolvedPromptId = promptId ?? 'checkout-assistant';
  const statsQuery = useQuery(productionStatsOptions(resolvedPromptId));
  const promptsQuery = useQuery(promptsOptions);
  const callsQuery = useQuery(callRecordsOptions);
  const rollback = useRollbackMutation();
  const [tracesOpen, setTracesOpen] = useState(false);
  const format = useLocaleFormatters();
  if (statsQuery.isPending || promptsQuery.isPending || callsQuery.isPending) return <QueryState state="loading" />;
  if (statsQuery.isError) return <QueryState state="error" onRetry={() => void statsQuery.refetch()} />;
  if (promptsQuery.isError) return <QueryState state="error" onRetry={() => void promptsQuery.refetch()} />;
  if (callsQuery.isError) return <QueryState state="error" onRetry={() => void callsQuery.refetch()} />;
  const stats = statsQuery.data;
  const prompt = promptsQuery.data?.find((item) => item.id === resolvedPromptId);
  if (!stats || !prompt) return <QueryState state="empty" />;
  const filteredCalls = callsQuery.data.filter((record) => record.versionId === `rev_checkout_${stats.currentRevision.replace(/^r/, '')}`);
  const quality = new Intl.NumberFormat('en-US', { style: 'percent' }).format(stats.quality);
  const errorRate = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 }).format(stats.errorRate);
  const handleRollback = () => {
    rollback.mutate(
      { promptId: resolvedPromptId, revisionId: `rev_${resolvedPromptId.replace(/-/g, '_')}_${stats.previousRevision.replace(/^r/, '')}` },
      {
        onSuccess: () => void navigate(`/app/prompts/${resolvedPromptId}`),
      },
    );
  };
  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.productionView.productionLabel', { version: stats.currentRevision })}
        title={prompt.title}
        description={t('lifecycle.productionView.previousLabel', { version: stats.previousRevision })}
      />
      {rollback.isSuccess ? (
        <Notification title={t('lifecycle.productionView.rollbackSuccessTitle', { version: stats.previousRevision })}>
          {t('lifecycle.productionView.rollbackSuccessBody')}
        </Notification>
      ) : null}
      {rollback.isError ? (
        <Notification tone="error" title={t('lifecycle.states.error.title')}>
          {t('lifecycle.productionView.rollbackError')}
        </Notification>
      ) : null}
      <Card title={t('lifecycle.productionView.traffic')}>
        <TrafficBar percent={stats.trafficPercent} />
      </Card>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="relative">
          <MetricTile label={t('lifecycle.productionView.quality')} value={quality} />
          <HelpIcon title={t('lifecycle.help.metrics.faithfulness')} className="absolute right-2 top-2">
            <p>{t('lifecycle.help.metrics.faithfulness')}</p>
          </HelpIcon>
        </div>
        <MetricTile label={t('lifecycle.productionView.avgCost')} value={format.currency(stats.avgCost)} />
        <MetricTile label={t('lifecycle.productionView.errorRate')} value={errorRate} />
      </div>
      <TopErrorRow stats={stats} />
      <div className="flex flex-wrap justify-end gap-3">
        <Button type="button" intent="neutral" leadingIcon={<ListChecks aria-hidden className="size-4" />} onClick={() => setTracesOpen(true)}>
          {t('lifecycle.productionView.viewTraces')}
        </Button>
        <Button
          type="button"
          intent="warning"
          leadingIcon={<ArrowUUpLeft aria-hidden className="size-4" />}
          onClick={handleRollback}
          loading={rollback.isPending}
        >
          {t('lifecycle.productionView.rollbackTo', { version: stats.previousRevision })}
        </Button>
        <HelpIcon title={t('lifecycle.help.rollback.title')}>
          <p>{t('lifecycle.help.rollback.body')}</p>
        </HelpIcon>
      </div>
      <Modal
        open={tracesOpen}
        title={t('lifecycle.productionView.tracesTitle')}
        description={t('lifecycle.productionView.tracesDescription')}
        confirmLabel={t('common.confirm')}
        onClose={() => setTracesOpen(false)}
        onConfirm={() => setTracesOpen(false)}
      />
      {filteredCalls.length > 0 ? (
        <Card title={t('lifecycle.productionView.tracesTitle')}>
          <TracesList records={filteredCalls} />
        </Card>
      ) : (
        <Card title={t('lifecycle.productionView.tracesTitle')}>
          <p className="text-body text-muted">{t('lifecycle.states.empty.description')}</p>
        </Card>
      )}
    </div>
  );
}