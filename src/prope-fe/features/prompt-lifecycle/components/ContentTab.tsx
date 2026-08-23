import { Gauge } from '@phosphor-icons/react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Drawer } from '@/components/ui/Drawer';
import { ApiKeyDemoCard } from '@/features/prompt-lifecycle/components/ApiKeyDemoCard';
import { ContentDiffSection } from '@/features/prompt-lifecycle/components/ContentDiffSection';
import { LifecycleActionBar } from '@/features/prompt-lifecycle/components/LifecycleActionBar';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ReadinessPanel } from '@/features/prompt-lifecycle/components/ReadinessPanel';
import type { LifecycleSummary } from '@/features/prompt-lifecycle/lifecycleSummaryApi';
import { getReadinessCard } from '@/features/prompt-lifecycle/readinessApi';
import type { PromptDetail, Revision } from '@/features/prompt-lifecycle/types';

function nextHref(promptId: string, versionId: string, action: LifecycleSummary['next_action']) {
  const base = `/app/prompts/${encodeURIComponent(promptId)}?version=${encodeURIComponent(versionId)}`;
  if (action === 'run_evaluation') return `/app/prompts/${encodeURIComponent(promptId)}/evaluation/run?version=${encodeURIComponent(versionId)}&from=content&returnTo=${encodeURIComponent(base)}`;
  if (action === 'edit_prompt') return `/app/prompts/${encodeURIComponent(promptId)}/edit?version=${encodeURIComponent(versionId)}&from=content&returnTo=${encodeURIComponent(base)}`;
  if (action === 'view_activity') return `${base}&tab=logs`;
  return `${base}&tab=monitoring#improvements`;
}

interface ContentTabProps {
  prompt: PromptDetail;
  revision: Revision;
  summary: LifecycleSummary;
}

/**
 * The Content tab: what the prompt says (by block), how it differs from the
 * previous revision, whether it is ready, and the snippet + key that put it to
 * work — everything a reader needs to judge and use this exact version.
 */
export function ContentTab({ prompt, revision, summary }: ContentTabProps) {
  const { t } = useTranslation();
  const [readinessOpen, setReadinessOpen] = useState(false);
  const readiness = useQuery({ queryKey: ['readiness', prompt.id, revision.id, 'edit'], queryFn: () => getReadinessCard(prompt.id, revision.id, 'edit') });
  if (readiness.isPending) return <QueryState state="loading" />;
  const findings = readiness.data?.findings.filter((item) => !item.dismissed).slice(0, 3) ?? [];

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-5 p-4 pb-24 sm:p-6">
      <section aria-labelledby="prompt-content-heading" className="rounded-modal border border-border bg-surface shadow-panel">
        <div className="border-b border-border p-4 sm:p-5">
          <h2 id="prompt-content-heading" className="font-display text-heading-3 text-ink">{t('lifecycle.surface.promptContent')}</h2>
        </div>
        <div className="p-4 sm:p-5"><PromptBlockAccordion body={revision.promptBody} /></div>
      </section>

      <ContentDiffSection revisions={prompt.revisions} selectedId={revision.id} />

      <section className="rounded-modal border border-border bg-surface p-4 shadow-panel sm:p-5" aria-labelledby="readiness-summary-heading">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="readiness-summary-heading" className="font-display text-heading-3 text-ink">{t('lifecycle.surface.readiness')}</h2>
            <p className="mt-1 text-body text-muted">{t('lifecycle.surface.readinessCount', { count: findings.length })}</p>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-control text-caption font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"
            onClick={() => setReadinessOpen(true)}
          >
            <Gauge aria-hidden className="size-4" />
            {t('lifecycle.surface.viewReadiness')}
          </button>
        </div>
        {readiness.isError ? (
          <p className="mt-3 text-caption text-danger-text">{t('lifecycle.surface.readinessUnavailable')}</p>
        ) : findings.length ? (
          <ul className="mt-4 grid gap-2">
            {findings.map((finding) => (
              <li key={finding.rule_id} className="rounded-control bg-subtle p-3 text-body text-ink">{t(`readiness.rule.${finding.rule_id}.title`)}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-body text-muted">{t('lifecycle.surface.noReadinessIssues')}</p>
        )}
      </section>

      <ApiKeyDemoCard modelName={prompt.modelName} released={summary.live_version_id !== null} />

      <LifecycleActionBar next={{ href: nextHref(prompt.id, revision.id, summary.next_action), label: t(`lifecycle.surface.actions.${summary.next_action}`) }} />

      <Drawer open={readinessOpen} onClose={() => setReadinessOpen(false)} side="right" size="wide" title={t('lifecycle.surface.readiness')}>
        <div className="h-full overflow-y-auto p-5"><ReadinessPanel promptId={prompt.id} versionId={revision.id} trigger="edit" /></div>
      </Drawer>
    </div>
  );
}
