import { Minus, TrendDown, TrendUp } from '@phosphor-icons/react';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface EvaluationMetricCardProps { label: string; value: number; trend: 'improving' | 'stable' | 'declining'; change?: number; }

export function EvaluationMetricCard({ label, value, trend, change }: EvaluationMetricCardProps) {
  const format = useLocaleFormatters();
  const Icon = trend === 'improving' ? TrendUp : trend === 'declining' ? TrendDown : Minus;
  return <article className="rounded-modal border border-border bg-surface p-4 shadow-panel"><p className="text-caption text-muted">{label}</p><div className="mt-1 flex items-end justify-between"><strong className="font-display text-heading-2 font-normal text-ink">{format.percent(value)}</strong>{change !== undefined ? <span className={cn('flex items-center gap-1 text-caption', trend === 'improving' ? 'text-success-text' : trend === 'declining' ? 'text-danger-text' : 'text-muted')}><Icon aria-hidden className="size-4" />{change > 0 ? '+' : ''}{format.number(change)}%</span> : null}</div></article>;
}
