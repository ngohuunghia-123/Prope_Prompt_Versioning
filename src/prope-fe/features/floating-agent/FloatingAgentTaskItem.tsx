import { CheckCircle, HourglassMedium, SpinnerGap, Stop, WarningCircle, X } from '@phosphor-icons/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { cancelEvaluationRun } from '@/features/floating-agent/api';
import type { FloatingAgentEvent } from '@/features/floating-agent/types';
import { AgentRunGraph } from '@/features/floating-agent/AgentRunGraph';
import { agentRunOptions, floatingAgentEventsOptions } from '@/features/floating-agent/queries';

export function FloatingAgentTaskItem({ event }: { event: FloatingAgentEvent }) {
  const { t } = useTranslation();
  const { dismiss } = useFloatingAgent();
  const client = useQueryClient();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const inProgress = event.type === 'progress' && !event.runId.startsWith('floating-agent-');
  // Running evaluation tasks need the run's shape even with the graph closed:
  // the eval run id the cancel button targets lives in the run's source refs.
  const details = useQuery({ ...agentRunOptions(event.runId), enabled: (detailsOpen || inProgress) && !event.runId.startsWith('floating-agent-') });
  const evalRunId = details.data?.kind === 'evaluation'
    ? details.data.source_refs.find((ref) => ref.startsWith('eval:'))?.slice('eval:'.length)
    : undefined;
  const cancelEval = useMutation({
    mutationFn: cancelEvaluationRun,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: agentRunOptions(event.runId).queryKey });
      void client.invalidateQueries({ queryKey: floatingAgentEventsOptions.queryKey });
    },
  });
  const progress = event.progress;
  const width = progress && progress.total > 0 ? `${Math.round((progress.current / progress.total) * 100)}%` : undefined;
  const progressKey = progress?.unit === 'items' ? 'floatingAgent.progress.items' : 'floatingAgent.progress.cases';

  return (
    <article className="flex items-start gap-3 py-3 first:pt-0 last:pb-0" aria-live={event.type === 'warning' ? 'assertive' : 'polite'}>
      <span className="mt-0.5 text-info-strong">
        {event.type === 'progress' ? <SpinnerGap aria-hidden className="size-5 animate-spin motion-reduce:animate-none" /> : event.type === 'attention' ? <HourglassMedium aria-hidden weight="fill" className="size-5 text-info-strong" /> : event.type === 'success' ? <CheckCircle aria-hidden weight="fill" className="size-5 text-success-text" /> : <WarningCircle aria-hidden weight="fill" className="size-5 text-warning-text" />}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-body font-semibold text-ink">{t(event.titleKey)}</h3>
        <p className="text-caption text-muted">{t(event.messageKey)}</p>
        {progress && progress.total > 0 ? (
          <div className="mt-2">
            <div className="h-1.5 overflow-hidden rounded-full bg-subtle">
              <div className="h-full rounded-full bg-info-strong transition-[width] motion-reduce:transition-none" style={{ width }} />
            </div>
            <span className="mt-1 block text-overline font-semibold text-muted">{t(progressKey, progress)}</span>
          </div>
        ) : null}
        {event.action ? <Link to={event.action.href} className="mt-2 inline-flex text-caption font-semibold text-link underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-focus">{t(event.action.labelKey)}</Link> : null}
        {!event.runId.startsWith('floating-agent-') ? <Button type="button" intent="ghost" size="small" className="mt-2" onClick={() => setDetailsOpen((open) => !open)}>{t(detailsOpen ? 'floatingAgent.graph.hide' : 'floatingAgent.graph.show')}</Button> : null}
        {detailsOpen && details.isPending ? <p className="mt-2 text-caption text-muted">{t('common.loading')}</p> : null}
        {detailsOpen && details.data ? <AgentRunGraph run={details.data} /> : null}
      </div>
      {event.type === 'progress' && evalRunId ? (
        <Button
          type="button"
          intent="ghost"
          size="floatingAgentIcon"
          loading={cancelEval.isPending}
          onClick={() => cancelEval.mutate(evalRunId)}
          aria-label={t('floatingAgent.cancelEval')}
        >
          <Stop aria-hidden weight="fill" className="size-4" />
        </Button>
      ) : null}
      {event.dismissible ? <Button type="button" intent="ghost" size="floatingAgentIcon" onClick={() => dismiss(event.runId)} aria-label={t('floatingAgent.dismiss')}><X aria-hidden className="size-4" /></Button> : null}
    </article>
  );
}
