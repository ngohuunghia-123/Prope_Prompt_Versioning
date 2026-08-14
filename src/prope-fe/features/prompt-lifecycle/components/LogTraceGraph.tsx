import { Brain, ChatCircleText, Database, Robot, Sparkle, Wrench } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

interface TraceNodeProps {
  icon: ReactNode;
  label: string;
  count?: number;
  emphasis?: boolean;
}

function TraceNode({ icon, label, count, emphasis = false }: TraceNodeProps) {
  return (
    <div className={cn('flex min-h-12 items-center justify-center gap-2 rounded-xl border px-3 py-2 text-center text-caption font-semibold shadow-inset', emphasis ? 'border-secondary bg-accent-soft text-ink' : 'border-border bg-surface text-ink')}>
      <span className="text-secondary">{icon}</span>
      <span>{label}</span>
      {count && count > 1 ? <span className="rounded-full bg-secondary px-1.5 py-0.5 text-overline text-inverse">×{count}</span> : null}
    </div>
  );
}

function Connector() {
  return <div aria-hidden className="mx-auto h-5 border-l border-border-strong" />;
}

interface LogTraceGraphProps { mode: 'aggregated' | 'expanded'; }

export function LogTraceGraph({ mode }: LogTraceGraphProps) {
  const { t } = useTranslation();
  const nodes = t('lifecycle.overview.logs.traceNodes', { returnObjects: true }) as Record<string, string>;
  return (
    <div className="mx-auto w-full max-w-lg rounded-modal bg-subtle/45 p-4 sm:p-6">
      <TraceNode icon={<ChatCircleText className="size-4" />} label={nodes.userInput ?? ''} />
      <Connector />
      <TraceNode icon={<Robot className="size-4" />} label={nodes.orchestrator ?? ''} emphasis />
      <Connector />
      <div className={cn('grid gap-3', mode === 'expanded' ? 'sm:grid-cols-3' : 'grid-cols-2')}>
        {mode === 'expanded' ? (
          <>
            <TraceNode icon={<Wrench className="size-4" />} label={nodes.searchTool ?? ''} />
            <TraceNode icon={<Wrench className="size-4" />} label={nodes.searchTool ?? ''} />
          </>
        ) : <TraceNode icon={<Wrench className="size-4" />} label={nodes.searchTool ?? ''} count={2} />}
        <TraceNode icon={<Database className="size-4" />} label={nodes.retrieveDocs ?? ''} />
      </div>
      <Connector />
      <TraceNode icon={<Brain className="size-4" />} label={nodes.reasoningAgent ?? ''} />
      <Connector />
      <TraceNode icon={<Sparkle className="size-4" />} label={nodes.llmGeneration ?? ''} />
      <Connector />
      <TraceNode icon={<ChatCircleText className="size-4" />} label={nodes.finalAnswer ?? ''} emphasis />
    </div>
  );
}
