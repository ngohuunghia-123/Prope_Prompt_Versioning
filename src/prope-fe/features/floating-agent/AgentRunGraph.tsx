import { ArrowDown } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { AgentRun } from '@/features/floating-agent/types';

export function AgentRunGraph({ run }: { run: AgentRun }) {
  const { t } = useTranslation();
  return (
    <section className="mt-3 rounded-control border border-border bg-canvas p-3" aria-label={t('floatingAgent.graph.title')}>
      <p className="text-overline text-muted">{t(`floatingAgent.planBasis.${run.plan_basis}`)}</p>
      <ol className="mt-2 grid gap-1">
        {run.nodes.map((node, index) => (
          <li key={node.id} className="grid justify-items-start gap-1">
            {index > 0 ? <ArrowDown aria-hidden className="ml-3 size-3 text-muted" /> : null}
            <div className="w-full rounded-control border border-border bg-surface p-2">
              <span className="block text-caption font-semibold text-ink">{t(`floatingAgent.capabilities.${node.capability}`)}</span>
              <span className="text-overline text-muted">{t(`floatingAgent.nodeKind.${node.kind}`)} · {t(`floatingAgent.nodeStatus.${node.status}`, { defaultValue: node.status })}</span>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-overline text-muted">{t('floatingAgent.graph.limit')}</p>
    </section>
  );
}
