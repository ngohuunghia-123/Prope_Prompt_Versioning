import { ClockCounterClockwise, ListMagnifyingGlass } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { ImprovementFindingList } from '@/features/prompt-lifecycle/components/ImprovementFindingList';
import { LogDetailDrawer } from '@/features/prompt-lifecycle/components/LogDetailDrawer';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { PromptLogTable } from '@/features/prompt-lifecycle/components/PromptLogTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { useMonitoringImprovement } from '@/features/prompt-lifecycle/components/useMonitoringImprovement';
import type { CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import type { ImprovementFinding } from '@/features/prompt-lifecycle/improvementTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface Props { promptId: string; revisionId: string; revisionLabel: string; isReleased: boolean | undefined; focusImprovement: boolean; onOpenEditor: (body: string, findingId: string) => void; }

function FindingList({ findings, monitor }: { findings: ImprovementFinding[]; monitor: ReturnType<typeof useMonitoringImprovement> }) {
  return <ImprovementFindingList findings={findings} busy={monitor.busy} onDismissFinding={async (findingId, reason) => { await monitor.dismissOne.mutateAsync({ findingId, reason }); }} onAcceptProposal={monitor.acceptProposalForFinding} onDismissProposal={async (proposalId, reason) => { await monitor.refuse.mutateAsync({ proposalId, reason }); }} />;
}

export function MonitoringImprovementTab({ promptId, revisionId, revisionLabel, isReleased, focusImprovement, onOpenEditor }: Props) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const [drawer, setDrawer] = useState<'logs' | 'history'>();
  const [selected, setSelected] = useState<CallRecord>();
  const improvementsRef = useRef<HTMLElement>(null);
  const monitor = useMonitoringImprovement(promptId, onOpenEditor);
  const openFindings = (monitor.findings.data ?? []).filter((item) => item.status === 'open').slice(0, 3);
  const history = (monitor.findings.data ?? []).filter((item) => item.status !== 'open');
  const usage = monitor.usage.data;
  const errorCount = usage?.buckets.reduce((sum, bucket) => sum + bucket.error_count, 0);
  const fallbackCount = usage?.buckets.reduce((sum, bucket) => sum + bucket.fallback_count, 0);
  const costByCurrency = new Map<string, number>();
  for (const bucket of usage?.buckets ?? []) for (const cost of bucket.cost) costByCurrency.set(cost.currency, (costByCurrency.get(cost.currency) ?? 0) + cost.amount);
  const costs = [...costByCurrency].map(([currency, amount]) => ({ currency, amount }));
  const latencies = (monitor.calls.data ?? []).flatMap((call) => call.upstream_duration_ms === null ? [] : [call.upstream_duration_ms]);
  const recentLatency = latencies.length ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length) : null;
  useEffect(() => {
    if (!focusImprovement) return;
    requestAnimationFrame(() => { improvementsRef.current?.focus(); improvementsRef.current?.scrollIntoView({ block: 'center' }); });
  }, [focusImprovement]);

  if (isReleased === undefined || monitor.usage.isPending || monitor.calls.isPending || monitor.findings.isPending) return <QueryState state="loading" />;
  if (monitor.usage.isError || monitor.calls.isError || monitor.findings.isError) return <QueryState state="error" onRetry={() => void Promise.all([monitor.usage.refetch(), monitor.calls.refetch(), monitor.findings.refetch()])} />;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-5 p-4 pb-24 sm:p-6">
      <section aria-labelledby="monitoring-heading" className="rounded-modal border border-border bg-surface p-5 shadow-panel">
        <h1 id="monitoring-heading" tabIndex={-1} className="font-display text-heading-2 text-ink">{t('lifecycle.surface.monitoring.title')}</h1>
        {!isReleased ? <p className="mt-2 text-body text-muted">{t('lifecycle.surface.monitoring.notLive')}</p> : !usage?.total_requests ? <p className="mt-2 text-body text-muted">{t('lifecycle.surface.monitoring.notEnoughData')}</p> : (
          <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.volume')}</dt><dd className="mt-1 text-heading-3 text-ink">{format.number(usage.total_requests)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.errors')}</dt><dd className="mt-1 text-heading-3 text-ink">{format.number(errorCount ?? 0)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.fallbacks')}</dt><dd className="mt-1 text-heading-3 text-ink">{format.number(fallbackCount ?? 0)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.latency')}</dt><dd className="mt-1 text-heading-3 text-ink">{recentLatency === null ? t('lifecycle.surface.notAvailable') : format.duration(recentLatency)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.cost')}</dt><dd className="mt-1 text-body font-semibold text-ink">{format.costs(costs) ?? t('lifecycle.surface.notAvailable')}</dd></div>
          </dl>
        )}
      </section>
      <section ref={improvementsRef} id="improvements" className="rounded-modal border border-border bg-surface shadow-panel" tabIndex={focusImprovement ? -1 : undefined}>
        <div className="border-b border-border p-5"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.monitoring.improvements')}</h2></div>
        {openFindings.length ? <FindingList findings={openFindings} monitor={monitor} /> : <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noOpenFindings')}</p>}
      </section>
      <section className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel"><div className="border-b border-border p-5"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.monitoring.recentLogs')}</h2></div>{monitor.calls.data?.length ? <PromptLogTable records={monitor.calls.data} selectedId={selected?.call_id} onSelect={setSelected} /> : <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noLogs')}</p>}</section>
      <div className="flex flex-wrap gap-2"><Button type="button" intent="ghost" size="small" leadingIcon={<ListMagnifyingGlass aria-hidden className="size-4" />} onClick={() => setDrawer('logs')}>{t('lifecycle.surface.monitoring.allLogs')}</Button><Button type="button" intent="ghost" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setDrawer('history')}>{t('lifecycle.surface.monitoring.history')}</Button></div>
      <Drawer open={drawer === 'logs'} onClose={() => setDrawer(undefined)} side="right" size="wide" title={t('lifecycle.surface.monitoring.allLogs')}><div className="h-full overflow-y-auto"><LogsTab promptId={promptId} revisionId={revisionId} revisionLabel={revisionLabel} /></div></Drawer>
      <Drawer open={drawer === 'history'} onClose={() => setDrawer(undefined)} side="right" size="wide" title={t('lifecycle.surface.monitoring.history')}><div className="h-full overflow-y-auto">{history.length ? <FindingList findings={history} monitor={monitor} /> : <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noHistory')}</p>}</div></Drawer>
      <LogDetailDrawer promptId={promptId} record={selected} onClose={() => setSelected(undefined)} />
    </div>
  );
}
