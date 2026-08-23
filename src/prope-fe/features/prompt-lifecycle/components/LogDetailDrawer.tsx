import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { SegmentedControl } from '@/components/SegmentedControl';
import { Drawer } from '@/components/ui/Drawer';
import { LogContentPanel } from '@/features/prompt-lifecycle/components/LogContentPanel';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { RequestConversation } from '@/features/prompt-lifecycle/components/RequestConversation';
import { TraceTimeline } from '@/features/prompt-lifecycle/components/TraceTimeline';
import type { CallRecord } from '@/features/prompt-lifecycle/insightsTypes';
import { callObservabilityOptions, lifecycleKeys } from '@/features/prompt-lifecycle/queries';

type DetailTab = 'content' | 'request' | 'trace';

interface LogDetailDrawerProps {
  promptId: string;
  record?: CallRecord;
  onClose: () => void;
}

export function LogDetailDrawer({ promptId, record, onClose }: LogDetailDrawerProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<DetailTab>('content');
  const callId = record?.call_id ?? '';
  const includeRequest = activeTab === 'request';
  const observability = useQuery({
    ...callObservabilityOptions(promptId, callId, includeRequest),
    enabled: Boolean(record) && activeTab !== 'content',
  });

  useEffect(() => setActiveTab('content'), [callId]);
  useEffect(() => {
    if (!record || includeRequest) return;
    queryClient.removeQueries({ queryKey: lifecycleKeys.callObservability(promptId, callId, true), exact: true });
  }, [callId, includeRequest, promptId, queryClient, record]);

  const close = () => {
    queryClient.removeQueries({ queryKey: lifecycleKeys.callObservability(promptId, callId, true), exact: true });
    onClose();
  };

  const options = (['content', 'request', 'trace'] as const).map((value) => ({
    value,
    label: t(`lifecycle.insights.trace.tabs.${value}`),
  }));

  return (
    <Drawer open={Boolean(record)} onClose={close} side="right" size="wide" title={t('lifecycle.insights.logs.logDetail')}>
      {record ? (
        <div className="flex h-full min-h-0 flex-col">
          <div className="sticky top-0 z-10 border-b border-border bg-surface p-3 sm:px-6">
            <SegmentedControl
              name="call-detail-tab"
              label={t('lifecycle.insights.trace.detailTabs')}
              value={activeTab}
              onValueChange={(value) => setActiveTab(value as DetailTab)}
              options={options}
              className="mx-auto max-w-full"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            {activeTab === 'content' ? <LogContentPanel record={record} /> : null}
            {activeTab !== 'content' && observability.isPending ? <QueryState state="loading" loadingLayout="inline" /> : null}
            {activeTab !== 'content' && observability.isError ? (
              <QueryState state="error" onRetry={() => void observability.refetch()} />
            ) : null}
            {activeTab === 'trace' && observability.data ? <TraceTimeline trace={observability.data} /> : null}
            {activeTab === 'request' && observability.data ? (
              observability.data.request.status === 'available' ? (
                <RequestConversation messages={observability.data.request.messages} />
              ) : (
                <div className="grid min-h-56 place-items-center rounded-xl border border-dashed border-border p-6 text-center">
                  <div>
                    <h3 className="font-display text-heading-3 text-ink">{t(`lifecycle.insights.trace.requestState.${observability.data.request.status}.title`)}</h3>
                    <p className="mt-2 text-body text-muted">{t(`lifecycle.insights.trace.requestState.${observability.data.request.status}.description`)}</p>
                  </div>
                </div>
              )
            ) : null}
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
