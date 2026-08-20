import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { TraceTimeline } from '@/features/prompt-lifecycle/components/TraceTimeline';
import { traceDetailOptions } from '@/features/prompt-lifecycle/queries';

interface EvaluationTracePanelProps {
  caseResultId: string;
  failed: boolean;
}

export function EvaluationTracePanel({ caseResultId, failed }: EvaluationTracePanelProps) {
  const { t } = useTranslation();
  const query = useQuery(traceDetailOptions(caseResultId, 'evaluation', failed));

  return (
    <section className="grid gap-2 border-t border-border pt-4">
      <h4 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">
        {t('lifecycle.insights.trace.evaluationTitle')}
      </h4>
      {query.isPending ? (
        <QueryState state="loading" loadingLayout="card" />
      ) : query.isError ? (
        <QueryState state="error" onRetry={() => void query.refetch()} />
      ) : (
        <TraceTimeline trace={query.data} />
      )}
    </section>
  );
}
