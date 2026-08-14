import { ArrowRight } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/StatusBadge';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { callRecordsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

interface PromptLogsPanelProps {
  promptId: string;
}

export function PromptLogsPanel({ promptId }: PromptLogsPanelProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const format = useLocaleFormatters();
  const query = useQuery(callRecordsOptions);

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;

  const records = query.data.filter((r) => r.promptTitle === promptId).slice(0, 10);

  if (records.length === 0) {
    return (
      <Card title={t('lifecycle.overview.tabs.logs')}>
        <p className="text-body text-muted">{t('lifecycle.states.empty.description')}</p>
        <div className="mt-4">
          <Button
            type="button"
            intent="neutral"
            trailingIcon={<ArrowRight aria-hidden className="size-4" />}
            onClick={() => void navigate(`/app/calls?promptId=${promptId}`)}
          >
            {t('lifecycle.detail.viewCalls')}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card title={t('lifecycle.overview.tabs.logs')}>
        <ul className="grid gap-2">
          {records.map((record) => (
            <li key={record.id} className="grid gap-1 rounded-lg border border-border bg-subtle p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <p className="text-body font-semibold text-ink">{record.promptTitle}</p>
                  <StatusBadge tone={record.outcome === 'success' ? 'active' : record.outcome === 'fallback' ? 'pending' : 'error'}>
                    {t(`lifecycle.calls.outcomes.${record.outcome}`)}
                  </StatusBadge>
                </div>
                <p className="text-caption text-muted">{format.date(record.timestamp)}</p>
              </div>
              <p className="text-caption text-muted">{record.consumer} · {format.number(record.tokens)} tokens · {format.currency(record.cost)}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Button
        type="button"
        intent="neutral"
        trailingIcon={<ArrowRight aria-hidden className="size-4" />}
        onClick={() => void navigate(`/app/calls?promptId=${promptId}`)}
      >
        {t('lifecycle.detail.viewCalls')}
      </Button>
    </div>
  );
}
