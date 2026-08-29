import { ClockCounterClockwise, ListMagnifyingGlass } from '@phosphor-icons/react';
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { getProposalDetail } from '@/features/prompt-lifecycle/improvementApi';
import { ImprovementFindingList } from '@/features/prompt-lifecycle/components/ImprovementFindingList';
import { LogDetailDrawer } from '@/features/prompt-lifecycle/components/LogDetailDrawer';
import { LogsTab } from '@/features/prompt-lifecycle/components/LogsTab';
import { MonitorReleaseSection } from '@/features/prompt-lifecycle/components/MonitorReleaseSection';
import { PromptLogTable } from '@/features/prompt-lifecycle/components/PromptLogTable';
import { PropaiFindingCards } from '@/features/prompt-lifecycle/components/PropaiFindingCards';
import { PropaiFindingDrawer } from '@/features/prompt-lifecycle/components/PropaiFindingDrawer';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { useMonitoringImprovement } from '@/features/prompt-lifecycle/components/useMonitoringImprovement';
import type { CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import type { ImprovementFinding } from '@/features/prompt-lifecycle/improvementTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';
import { UsageProfileWizard } from '@/features/prompt-lifecycle/components/UsageProfileWizard';

interface Props {
  promptId: string;
  revisionId: string;
  currentBody: string;
  revisionLabel: string;
  revisionLabels: Record<string, string>;
  releasedVersionId: string | null;
  focusImprovement: boolean;
  focusFindingId?: string;
  onOpenEditor: (body: string, findingId: string) => void;
}

function FindingHistoryList({ findings, monitor }: { findings: ImprovementFinding[]; monitor: ReturnType<typeof useMonitoringImprovement> }) {
  return (
    <ImprovementFindingList
      findings={findings}
      busy={monitor.busy}
      onDismissFinding={async (findingId, reason) => { await monitor.dismissOne.mutateAsync({ findingId, reason }); }}
      onAcceptProposal={monitor.acceptProposalForFinding}
      onDismissProposal={async (proposalId, reason) => { await monitor.refuse.mutateAsync({ proposalId, reason }); }}
    />
  );
}

/**
 * The Monitor & Improve tab: release state on top, then the four summary tiles,
 * the PropAI suggestion cards opening the before/after drawer, and the recent
 * calls table. Availability is computed from the same buckets as the error
 * count — one source of truth for "how often did this fail".
 */
export function MonitoringImprovementTab({ promptId, revisionId, currentBody, revisionLabel, revisionLabels, releasedVersionId, focusImprovement, focusFindingId, onOpenEditor }: Props) {
  const { t } = useTranslation();
  const format = useInsightsFormat();
  const [logsOpen, setLogsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selected, setSelected] = useState<ImprovementFinding>();
  const [selectedCall, setSelectedCall] = useState<CallRecord>();
  const monitor = useMonitoringImprovement(promptId, onOpenEditor);

  const findingData = monitor.findings.data;
  const findings = findingData ?? [];
  const openFindings = findings.filter((item) => item.status === 'open').slice(0, 3);
  const history = findings.filter((item) => item.status !== 'open');
  const usage = monitor.usage.data;
  const totalRequests = usage?.total_requests ?? 0;
  const errorCount = usage?.buckets.reduce((sum, bucket) => sum + bucket.error_count, 0) ?? 0;
  const availability = totalRequests > 0 ? (totalRequests - errorCount) / totalRequests : null;
  const costByCurrency = new Map<string, number>();
  for (const bucket of usage?.buckets ?? []) {
    for (const cost of bucket.cost) costByCurrency.set(cost.currency, (costByCurrency.get(cost.currency) ?? 0) + cost.amount);
  }
  const costs = [...costByCurrency].map(([currency, amount]) => ({ currency, amount }));
  const latencies = (monitor.calls.data ?? []).flatMap((call) => call.upstream_duration_ms === null ? [] : [call.upstream_duration_ms]);
  const avgLatency = latencies.length ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length) : null;

  useEffect(() => {
    if (!focusFindingId) return;
    const focused = findingData?.find((finding) => finding.finding_id === focusFindingId);
    if (focused) setSelected(focused);
  }, [findingData, focusFindingId]);

  // ADR-0070: the one pre-decision body read, fetched when a proposal's card
  // opens. The inbox row stays metadata-only; an `llm_edit` card does not
  // render its accept button until THIS query has put the candidate body and
  // its diff on the screen.
  const proposalId = selected?.proposal?.proposal_id;
  const detail = useQuery({
    queryKey: ['improvement-proposal', proposalId],
    queryFn: () => getProposalDetail(proposalId!),
    enabled: Boolean(proposalId),
    staleTime: 30_000,
  });
  const selectedWithBody = useMemo(() => {
    if (!selected?.proposal || selected.proposal.candidate_body != null) return selected;
    if (detail.data?.candidate_body == null) return selected;
    return {
      ...selected,
      proposal: { ...selected.proposal, candidate_body: detail.data.candidate_body },
    };
  }, [selected, detail.data]);

  if (monitor.usage.isPending || monitor.calls.isPending || monitor.findings.isPending) return <QueryState state="loading" />;
  if (monitor.usage.isError || monitor.calls.isError || monitor.findings.isError) return <QueryState state="error" onRetry={() => void Promise.all([monitor.usage.refetch(), monitor.calls.refetch(), monitor.findings.refetch()])} />;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-5 p-4 pb-24 sm:p-6">
      <section aria-labelledby="monitoring-heading" className="rounded-modal border border-border bg-surface p-5 shadow-panel">
        <h1 id="monitoring-heading" tabIndex={-1} className="font-display text-heading-2 text-ink">{t('lifecycle.surface.monitoring.title')}</h1>
        {!usage?.total_requests ? (
          <p className="mt-2 text-body text-muted">{t('lifecycle.surface.monitoring.notEnoughData')}</p>
        ) : (
          <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.availability')}</dt><dd className="mt-1 text-heading-3 text-ink">{availability === null ? t('lifecycle.surface.notAvailable') : format.percent(availability)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.totalRequests')}</dt><dd className="mt-1 text-heading-3 text-ink">{format.number(totalRequests)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.avgLatency')}</dt><dd className="mt-1 text-heading-3 text-ink">{avgLatency === null ? t('lifecycle.surface.notAvailable') : format.duration(avgLatency)}</dd></div>
            <div className="rounded-control bg-subtle p-3"><dt className="text-caption text-muted">{t('lifecycle.surface.monitoring.totalCost')}</dt><dd className="mt-1 text-body font-semibold text-ink">{format.costs(costs) ?? t('lifecycle.surface.notAvailable')}</dd></div>
          </dl>
        )}
      </section>

      <UsageProfileWizard promptId={promptId} versionId={revisionId} />

      <MonitorReleaseSection promptId={promptId} versionId={revisionId} revisionLabel={revisionLabel} revisionLabels={revisionLabels} releasedVersionId={releasedVersionId} />

      <section id="improvements" className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel" tabIndex={focusImprovement ? -1 : undefined}>
        <div className="border-b border-border p-5"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.monitoring.propai.sectionTitle')}</h2></div>
        {openFindings.length ? (
          <PropaiFindingCards findings={openFindings} onSelect={setSelected} />
        ) : (
          <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noOpenFindings')}</p>
        )}
      </section>

      <section className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
        <div className="border-b border-border p-5"><h2 className="font-display text-heading-3 text-ink">{t('lifecycle.surface.monitoring.recentLogs')}</h2></div>
        {monitor.calls.data?.length ? (
          <PromptLogTable records={monitor.calls.data} selectedId={selectedCall?.call_id} onSelect={setSelectedCall} />
        ) : (
          <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noLogs')}</p>
        )}
      </section>

      <div className="flex flex-wrap gap-2">
        <Button type="button" intent="ghost" size="small" leadingIcon={<ListMagnifyingGlass aria-hidden className="size-4" />} onClick={() => setLogsOpen(true)}>
          {t('lifecycle.surface.monitoring.allLogs')}
        </Button>
        <Button type="button" intent="ghost" size="small" leadingIcon={<ClockCounterClockwise aria-hidden className="size-4" />} onClick={() => setHistoryOpen(true)}>
          {t('lifecycle.surface.monitoring.history')}
        </Button>
      </div>

      <Drawer open={logsOpen} onClose={() => setLogsOpen(false)} side="right" size="wide" title={t('lifecycle.surface.monitoring.allLogs')}>
        <div className="h-full overflow-y-auto"><LogsTab promptId={promptId} revisionId={revisionId} revisionLabel={revisionLabel} /></div>
      </Drawer>
      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} side="right" size="wide" title={t('lifecycle.surface.monitoring.history')}>
        <div className="h-full overflow-y-auto">
          {history.length ? (
            <FindingHistoryList findings={history} monitor={monitor} />
          ) : (
            <p className="p-5 text-body text-muted">{t('lifecycle.surface.monitoring.noHistory')}</p>
          )}
        </div>
      </Drawer>

      <LogDetailDrawer promptId={promptId} record={selectedCall} onClose={() => setSelectedCall(undefined)} />

      <PropaiFindingDrawer
        finding={selectedWithBody}
        currentBody={currentBody}
        busy={monitor.busy}
        detail={detail.data}
        onClose={() => setSelected(undefined)}
        onAccept={(proposalId) => void monitor.acceptProposalForFinding(proposalId)}
        onDismissProposal={(proposalId, reason) => void monitor.refuse.mutateAsync({ proposalId, reason })}
        onDismissFinding={(findingId, reason) => void monitor.dismissOne.mutateAsync({ findingId, reason })}
      />
    </div>
  );
}
