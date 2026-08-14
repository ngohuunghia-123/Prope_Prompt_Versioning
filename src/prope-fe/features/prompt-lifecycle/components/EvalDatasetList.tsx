import { CheckCircle, Play, Sparkle, XCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import type { EvalDatasetResult } from '@/features/prompt-lifecycle/types';

interface EvalDatasetListProps {
  datasets: EvalDatasetResult[];
  selectedId: string;
  runningId?: string;
  creating: boolean;
  onSelect: (datasetId: string) => void;
  onRun: (datasetId: string) => void;
  onCreateWithAi: () => void;
}

export function EvalDatasetList({ datasets, selectedId, runningId, creating, onSelect, onRun, onCreateWithAi }: EvalDatasetListProps) {
  const { t } = useTranslation();
  return (
    <aside className="flex min-h-0 flex-col rounded-modal border border-border bg-surface shadow-panel">
      <header className="border-b border-border px-4 py-3">
        <h2 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">{t('lifecycle.evalWorkspace.datasets')}</h2>
        <p className="mt-1 text-caption text-muted">{t('lifecycle.evalWorkspace.datasetsHint')}</p>
      </header>
      <div className="border-b border-border p-3">
        <Button className="w-full" type="button" intent="neutral" loading={creating} leadingIcon={<Sparkle aria-hidden className="size-4" weight="fill" />} onClick={onCreateWithAi}>
          {t('lifecycle.evalWorkspace.createWithAi')}
        </Button>
      </div>
      <div className="grid gap-2 overflow-y-auto p-3">
        {datasets.map((dataset) => {
          const passed = dataset.tests.filter((test) => test.passed).length;
          const selected = dataset.id === selectedId;
          return (
            <div key={dataset.id} className={cn('grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-xl border p-2 transition-colors', selected ? 'border-focus bg-accent-soft' : 'border-border bg-canvas hover:bg-subtle')}>
              <button type="button" onClick={() => onSelect(dataset.id)} className="min-w-0 rounded-lg px-2 py-1 text-left focus-visible:outline-2 focus-visible:outline-focus" aria-pressed={selected}>
                <span className="flex items-center gap-2">
                  {passed === dataset.tests.length ? <CheckCircle aria-hidden className="size-4 shrink-0 text-success-text" weight="fill" /> : <XCircle aria-hidden className="size-4 shrink-0 text-danger-text" weight="fill" />}
                  <span className="truncate text-body font-semibold text-ink">{dataset.name}</span>
                </span>
                <span className="mt-1 block line-clamp-2 text-caption text-muted">{dataset.description}</span>
                <span className="mt-2 block text-caption font-medium text-ink">{t('lifecycle.evalWorkspace.passCount', { passed, total: dataset.tests.length })}</span>
              </button>
              <Button
                type="button"
                intent="ghost"
                size="navigationIcon"
                loading={runningId === dataset.id}
                aria-label={t('lifecycle.evalWorkspace.runDataset', { name: dataset.name })}
                title={t('lifecycle.evalWorkspace.runDataset', { name: dataset.name })}
                onClick={() => onRun(dataset.id)}
              >
                <Play aria-hidden weight="fill" />
              </Button>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
