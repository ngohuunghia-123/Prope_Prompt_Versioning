import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { SegmentedControl } from '@/components/SegmentedControl';
import { Checkbox } from '@/components/ui/Checkbox';
import { ProductionMetrics } from '@/features/prompt-lifecycle/components/ProductionMetrics';
import { ProductionProductTable } from '@/features/prompt-lifecycle/components/ProductionProductTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import type { UsageWindow } from '@/features/prompt-lifecycle/insightsTypes';
import { promptUsageOptions } from '@/features/prompt-lifecycle/queries';

interface ProductionTabProps {
  promptId: string;
}

const WINDOWS: readonly UsageWindow[] = ['24h', '7d', '30d'];

/**
 * Which products are calling this prompt, in what proportion, at what cost.
 *
 * **Defaults to gateway traffic over thirty days.** Gateway because the tab is
 * about production and a person's own playground turns are not that; thirty days
 * because a share computed over all time ossifies — an app that stopped calling
 * last quarter would keep its slice forever.
 *
 * Including the internal caller is one checkbox, and turning it on raises the
 * totals to what the workspace actually spent on this prompt. Eval runs are not
 * among them: their ledger rows carry no `prompt_id`, so nothing per-prompt can
 * find them, and their cost is reported by the Eval tab instead.
 */
export function ProductionTab({ promptId }: ProductionTabProps) {
  const { t } = useTranslation();
  const [window, setWindow] = useState<UsageWindow>('30d');
  const [includeInternal, setIncludeInternal] = useState(false);
  const query = useQuery(promptUsageOptions(promptId, window, includeInternal ? null : 'gateway'));

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <SegmentedControl
          name="usage-window"
          label={t('lifecycle.insights.production.window')}
          value={window}
          onValueChange={(value) => setWindow(value as UsageWindow)}
          options={WINDOWS.map((value) => ({ value, label: t(`lifecycle.insights.windows.${value}`) }))}
          className="sm:max-w-96"
        />
        <Checkbox
          label={t('lifecycle.insights.production.includeInternal')}
          checked={includeInternal}
          onChange={(event) => setIncludeInternal(event.target.checked)}
        />
      </div>

      {query.isPending ? (
        <QueryState state="loading" />
      ) : query.isError ? (
        <QueryState state="error" onRetry={() => void query.refetch()} />
      ) : query.data.total_requests === 0 ? (
        <div className="rounded-modal border border-dashed border-border bg-surface p-8 text-center text-body text-muted">
          {t(
            includeInternal
              ? 'lifecycle.insights.production.emptyAll'
              : 'lifecycle.insights.production.emptyGateway',
          )}
        </div>
      ) : (
        <>
          <ProductionMetrics usage={query.data} />
          <ProductionProductTable buckets={query.data.buckets} totalRequests={query.data.total_requests} />
        </>
      )}
    </div>
  );
}
