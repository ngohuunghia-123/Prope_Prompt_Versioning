import { CaretDown } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { TraceTimeline } from '@/features/prompt-lifecycle/components/TraceTimeline';
import { evalCaseTraceOptions } from '@/features/prompt-lifecycle/queries';
import { cn } from '@/lib/cn';

interface EvaluationTracePanelProps {
  runId: string;
  caseResultId: string;
}

export function EvaluationTracePanel({ runId, caseResultId }: EvaluationTracePanelProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(() => window.matchMedia('(min-width: 768px)').matches);
  const query = useQuery({ ...evalCaseTraceOptions(runId, caseResultId), enabled: expanded });

  return (
    <section className="grid gap-3 border-t border-border pt-4">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        className="flex min-h-10 w-full cursor-pointer items-center justify-between gap-3 rounded-lg text-left focus-visible:outline-2 focus-visible:outline-focus"
      >
        <span className="text-overline font-bold uppercase tracking-navigation-overline text-muted">
          {t('lifecycle.insights.trace.evaluationTitle')}
        </span>
        <CaretDown aria-hidden className={cn('size-4 text-muted transition-transform', expanded && 'rotate-180')} />
      </button>
      {expanded && query.isPending ? <QueryState state="loading" loadingLayout="inline" /> : null}
      {expanded && query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}
      {expanded && query.data ? <TraceTimeline trace={query.data} /> : null}
    </section>
  );
}
