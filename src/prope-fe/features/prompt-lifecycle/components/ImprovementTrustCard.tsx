import { CaretDown, CaretUp, CheckCircle, Circle, WarningCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import type { AgentRun } from '@/features/floating-agent/types';
import { cn } from '@/lib/cn';

interface ImprovementTrustCardProps {
  run: AgentRun;
  onReview: (findingId: string) => void;
  onRetry: () => void;
}

export function ImprovementTrustCard({ run, onReview, onRetry }: ImprovementTrustCardProps) {
  const { t } = useTranslation();
  // Collapsed unless the run is live: the header keeps the one-line status
  // ("review", "failed"…) so the progress timeline only earns its space
  // while the user is actually waiting on it — the rail below is what this
  // column is for.
  const [collapsed, setCollapsed] = useState(() => run.status !== 'queued' && run.status !== 'running');
  const action = run.result_actions[0];
  const findingId = action?.kind === 'open_improvement' ? action.finding_id : undefined;
  const proposalId = action?.proposal_id;
  const running = run.status === 'queued' || run.status === 'running';
  const missingResult = run.status === 'waiting_for_user' && !findingId;
  const failed = run.status === 'failed' || run.status === 'cancelled' || missingResult;
  // The limited-evidence copy is evidence-source specific: `no_live_usage` is
  // the production path's story, `gate_rejected` means the drafted edit was
  // tested and did not improve the suite, and the drafter/rails reasons mean
  // no suggestion was produced at all — never a usage-data story on the
  // eval-evidence run, which reads no usage data.
  const limitedReason = action?.kind === 'limited_evidence' ? action.reason : undefined;
  const titleKey = running ? 'running' : findingId ? 'review' : missingResult ? 'incomplete' : failed ? 'failed' : limitedReason === 'gate_rejected' ? 'gateRejected' : limitedReason ? 'incomplete' : run.status === 'warning' ? 'limited' : 'complete';

  return (
    <section className="border-b border-border bg-subtle p-4" aria-live="polite" aria-busy={running}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><p className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.promptDetail.improvementTrust.eyebrow')}</p><h3 className="mt-1 text-body font-semibold text-ink">{t(`lifecycle.promptDetail.improvementTrust.status.${titleKey}`)}</h3></div>
        <button type="button" className="grid size-8 shrink-0 place-items-center rounded-control text-muted hover:bg-surface focus-visible:outline-2 focus-visible:outline-focus" aria-label={collapsed ? t('floatingAgent.expand') : t('floatingAgent.collapse')} onClick={() => setCollapsed((value) => !value)}>{collapsed ? <CaretDown aria-hidden /> : <CaretUp aria-hidden />}</button>
      </div>
      {!collapsed ? <div className="mt-4 grid max-h-96 gap-4 overflow-y-auto">
        {!missingResult ? <ol className="relative grid gap-0 before:absolute before:top-3 before:bottom-3 before:left-2 before:w-px before:bg-border">
          {run.nodes.map((node) => {
            const done = node.status === 'succeeded';
            const warning = node.status === 'warning' || node.status === 'failed';
            return <li key={node.id} className="relative grid grid-cols-[1rem_1fr] gap-3 py-1.5"><span className={cn('relative z-10 mt-0.5 grid size-4 place-items-center rounded-full bg-surface', done && 'text-success', warning && 'text-danger', !done && !warning && 'text-muted')}>{done ? <CheckCircle aria-hidden weight="fill" /> : warning ? <WarningCircle aria-hidden weight="fill" /> : <Circle aria-hidden weight={node.status === 'running' ? 'fill' : 'regular'} />}</span><span><span className="block text-caption font-semibold text-ink">{t(`lifecycle.promptDetail.improvementTrust.steps.${node.capability}`, { defaultValue: t(`floatingAgent.capabilities.${node.capability}`) })}</span><span className="text-overline text-muted">{t(`floatingAgent.nodeStatus.${node.status}`, { defaultValue: node.status })}</span></span></li>;
          })}
        </ol> : null}
        <p className="text-caption text-muted">{t('lifecycle.promptDetail.improvementTrust.control')}</p>
        {proposalId && findingId ? <Button size="small" intent="neutral" onClick={() => onReview(findingId)}>{t('lifecycle.promptDetail.improvementTrust.reviewAction')}</Button> : null}
        {action?.kind === 'limited_evidence' ? <p className="rounded-control bg-warning p-3 text-caption text-warning-strong">{t(limitedReason === 'gate_rejected' ? 'lifecycle.promptDetail.improvementTrust.gateRejected' : limitedReason && limitedReason !== 'no_live_usage' ? 'lifecycle.promptDetail.improvementTrust.missingResult' : 'lifecycle.promptDetail.improvementTrust.limitedEvidence')}</p> : null}
        {action?.kind === 'no_change' ? <p className="rounded-control bg-success p-3 text-caption text-success-strong">{t('lifecycle.promptDetail.improvementTrust.noChange')}</p> : null}
        {missingResult ? <p className="rounded-control bg-warning p-3 text-caption text-warning-strong">{t('lifecycle.promptDetail.improvementTrust.missingResult')}</p> : null}
        {failed || (action?.kind === 'limited_evidence' && !running) ? <Button size="small" intent="neutral" onClick={onRetry}>{t('common.tryAgain')}</Button> : null}
      </div> : null}
    </section>
  );
}
