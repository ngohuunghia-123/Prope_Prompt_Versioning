import { CaretDown, CaretUp, CheckCircle, Circle, WarningCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import type { AgentRun } from '@/features/floating-agent/types';
import { draftIdForRun } from '@/features/prompt-lifecycle/draftApi';
import { cn } from '@/lib/cn';

interface ImprovementTrustCardProps {
  run: AgentRun;
  onReview: (findingId: string) => void;
  /** Opens the draft the run created, selected under its version in the rail. */
  onOpenDraft: (versionId: string, draftId: string) => void;
  /** The newest draft any recent run produced — the fallback link when THIS
   * run ended without one (rails refused every attempt), so the drafts the
   * feature did create never become unreachable from here. */
  latestDraft?: { versionId: string; draftId: string };
  onRetry: () => void;
}

export function ImprovementTrustCard({ run, onReview, onOpenDraft, latestDraft, onRetry }: ImprovementTrustCardProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const action = run.result_actions[0];
  // The run's gated candidate is parked as a draft under the version it
  // targeted — the id is derived from the run, so the link survives the
  // component remounting before the draft store is read.
  const draftedThisRun = action?.drafted === 'true' && Boolean(run.version_id);
  const draftTarget = draftedThisRun && run.version_id ? { versionId: run.version_id, draftId: draftIdForRun(run.run_id) } : latestDraft;
  const findingId = action?.kind === 'open_improvement' ? action.finding_id : undefined;
  const proposalId = action?.proposal_id;
  const running = run.status === 'queued' || run.status === 'running';
  const missingResult = run.status === 'waiting_for_user' && !findingId;
  const failed = run.status === 'failed' || run.status === 'cancelled' || missingResult;
  const titleKey = running ? 'running' : draftTarget ? 'draftReady' : findingId ? 'review' : missingResult ? 'incomplete' : failed ? 'failed' : run.status === 'warning' ? 'limited' : 'complete';

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
        {draftTarget ? (
          <div className="grid gap-2 rounded-control bg-success p-3">
            <p className="text-caption text-success-strong">{t(draftedThisRun ? 'lifecycle.promptDetail.improvementTrust.draftCreated' : 'lifecycle.promptDetail.improvementTrust.draftAvailable')}</p>
            <Button size="small" intent="primary" className="w-fit" onClick={() => onOpenDraft(draftTarget.versionId, draftTarget.draftId)}>
              {t('lifecycle.promptDetail.improvementTrust.reviewDraft')}
            </Button>
          </div>
        ) : null}
        {proposalId && findingId ? <Button size="small" onClick={() => onReview(findingId)}>{t('lifecycle.promptDetail.improvementTrust.reviewAction')}</Button> : null}
        {action?.kind === 'limited_evidence' ? <p className="rounded-control bg-warning p-3 text-caption text-warning-strong">{t('lifecycle.promptDetail.improvementTrust.limitedEvidence')}</p> : null}
        {action?.kind === 'no_change' && !draftTarget ? <p className="rounded-control bg-success p-3 text-caption text-success-strong">{t('lifecycle.promptDetail.improvementTrust.noChange')}</p> : null}
        {missingResult ? <p className="rounded-control bg-warning p-3 text-caption text-warning-strong">{t('lifecycle.promptDetail.improvementTrust.missingResult')}</p> : null}
        {failed || (action?.kind === 'limited_evidence' && !running) ? <Button size="small" intent="neutral" onClick={onRetry}>{t('common.tryAgain')}</Button> : null}
      </div> : null}
    </section>
  );
}
