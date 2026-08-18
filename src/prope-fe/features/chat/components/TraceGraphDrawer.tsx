import { useTranslation } from 'react-i18next';

import { Drawer } from '@/components/ui/Drawer';
import { TraceGraph } from '@/features/chat/components/TraceGraph';
import { usePipeline } from '@/features/chat/usePipeline';
import type { TraceEntry } from '@/features/chat/types';

/**
 * The graph, on demand.
 *
 * The pipeline arrives through {@link usePipeline}, which the trace list behind
 * this drawer is already holding — so opening the graph costs no request at all.
 *
 * The failure mode is deliberately quiet. Without the pipeline there is no graph
 * to draw, and the trace list in the panel behind this drawer is still there and
 * still correct — so this says so and stops, rather than rendering half a picture
 * of a turn somebody is trying to understand.
 */
export function TraceGraphDrawer({
  open,
  onClose,
  trace,
}: {
  open: boolean;
  onClose: () => void;
  trace: TraceEntry[];
}) {
  const { t } = useTranslation();
  const pipeline = usePipeline();

  return (
    <Drawer open={open} onClose={onClose} side="right" size="full" title={t('chat.graph.title')}>
      <div className="h-full overflow-y-auto p-5 sm:p-6">
        <h2 className="m-0 text-navigation-strong font-semibold text-ink">{t('chat.graph.title')}</h2>
        <p className="mt-1 mb-4 max-w-prose text-caption text-muted">{t('chat.graph.description')}</p>
        {pipeline ? (
          <TraceGraph pipeline={pipeline} trace={trace} />
        ) : (
          <p className="m-0 text-caption text-muted">{t('chat.graph.unavailable')}</p>
        )}
      </div>
    </Drawer>
  );
}
