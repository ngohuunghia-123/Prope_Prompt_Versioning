import { Brain, CaretDown, CheckCircle, Graph, Sparkle, Toolbox, WarningCircle } from '@phosphor-icons/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TraceGraphDrawer } from '@/features/chat/components/TraceGraphDrawer';
import type { ChatActivity, TraceEntry } from '@/features/chat/types';
import { cn } from '@/lib/cn';

interface ChatActivityTimelineProps {
  activities: ChatActivity[];
  trace?: TraceEntry[];
  streaming?: boolean;
}

export function ChatActivityTimeline({ activities, trace = [], streaming = false }: ChatActivityTimelineProps) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(streaming);
  const [graphOpen, setGraphOpen] = useState(false);

  useEffect(() => setOpen(streaming), [streaming]);
  if (!activities.length) return null;

  const active = [...activities].reverse().find((activity) => activity.status === 'running');
  const total = activities.reduce((sum, activity) => sum + (activity.latency_ms ?? 0), 0);
  const warning = activities.some((activity) => activity.status === 'warn' || activity.status === 'error');
  const summary = streaming && active
    ? t(active.label_code)
    : t('chat.activity.summary', { count: activities.length, duration: (total / 1000).toLocaleString(i18n.language, { maximumFractionDigits: 1 }) });

  return (
    <div className="rounded-navigation-panel border border-border bg-canvas/70">
      <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex w-full cursor-pointer items-center gap-2 rounded-navigation-panel px-2.5 py-2 text-left hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
        {streaming ? (
          <span className="size-8 shrink-0 overflow-hidden rounded-full bg-info">
            <img src="/assets/propai-thinking.gif" alt="" className="size-full object-cover motion-reduce:hidden" />
            <Sparkle aria-hidden className="hidden size-full p-1.5 text-info-strong motion-reduce:block" />
          </span>
        ) : warning ? <WarningCircle aria-hidden className="size-4 shrink-0 text-warning-text" /> : <CheckCircle aria-hidden className="size-4 shrink-0 text-success-text" />}
        <span className="min-w-0 flex-1 truncate text-overline font-semibold text-ink">{summary}</span>
        <CaretDown aria-hidden className={cn('size-4 shrink-0 text-muted transition-transform motion-reduce:transition-none', open && 'rotate-180')} />
      </button>
      {open ? (
        <div className="border-t border-border px-2.5 py-2">
          <ol className="grid gap-1.5">
            {activities.map((activity) => (
              <li key={activity.id} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 text-overline">
                {activity.kind === 'action' ? <Toolbox aria-hidden className="size-3.5 text-link" /> : <Brain aria-hidden className="size-3.5 text-secondary" />}
                <span className={cn('truncate text-muted', activity.status === 'running' && 'font-semibold text-ink')}>{t(activity.status === 'running' ? activity.label_code : `chat.activity.completed.${activity.label_code.replace('chat.activity.', '')}`, { defaultValue: t(activity.label_code) })}</span>
                <span className="tabular-nums text-muted">{activity.status === 'running' ? t('chat.activity.running') : activity.latency_ms !== undefined ? `${activity.latency_ms}ms` : ''}</span>
              </li>
            ))}
          </ol>
          {trace.length && !streaming ? (
            <button type="button" onClick={() => setGraphOpen(true)} className="mt-2 flex cursor-pointer items-center gap-1 text-overline text-link underline focus-visible:outline-2 focus-visible:outline-focus">
              <Graph aria-hidden className="size-3.5" />{t('chat.graph.open')}
            </button>
          ) : null}
        </div>
      ) : null}
      <TraceGraphDrawer open={graphOpen} onClose={() => setGraphOpen(false)} trace={trace} />
    </div>
  );
}
