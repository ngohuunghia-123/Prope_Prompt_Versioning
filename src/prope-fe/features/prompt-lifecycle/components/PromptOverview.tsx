import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs } from '@/components/Tabs';
import { EvaluationWorkflow } from '@/features/prompt-lifecycle/components/EvaluationWorkflow';
import { PromptContentPanel } from '@/features/prompt-lifecycle/components/PromptContentPanel';
import { PromptProductionLogs } from '@/features/prompt-lifecycle/components/PromptProductionLogs';
import { VersionHistoryPanel } from '@/features/prompt-lifecycle/components/VersionHistoryPanel';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';

type DetailTab = 'content' | 'evaluation' | 'logs';

export interface PromptOverviewProps { prompt: PromptDetail; }

export function PromptOverview({ prompt }: PromptOverviewProps) {
  const { t } = useTranslation();
  const [selectedRevisionId, setSelectedRevisionId] = useState(prompt.revisions[0]?.id ?? '');
  const [activeTab, setActiveTab] = useState<DetailTab>('content');
  const tabs = [
    { value: 'content', label: t('lifecycle.overview.tabs.content') },
    { value: 'evaluation', label: t('lifecycle.overview.tabs.evaluation') },
    { value: 'logs', label: t('lifecycle.overview.tabs.logs') },
  ];
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(16rem,0.8fr)_minmax(0,2.2fr)]">
      <VersionHistoryPanel prompt={prompt} selectedRevisionId={selectedRevisionId} onSelectRevision={setSelectedRevisionId} />
      <section aria-label={t('lifecycle.overview.detailPanel')} className="min-w-0 overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
        <Tabs items={tabs} value={activeTab} onValueChange={(value) => setActiveTab(value as DetailTab)} label={t('lifecycle.overview.tabLabel')} className="px-4 sm:px-6" />
        <div role="tabpanel" className="p-4 sm:p-6">
          {activeTab === 'content' ? <PromptContentPanel prompt={prompt} revisionId={selectedRevisionId} /> : null}
          {activeTab === 'evaluation' ? <EvaluationWorkflow promptId={prompt.id} /> : null}
          {activeTab === 'logs' ? <PromptProductionLogs promptId={prompt.id} promptTitle={prompt.title} revisionId={selectedRevisionId} /> : null}
        </div>
      </section>
    </div>
  );
}
