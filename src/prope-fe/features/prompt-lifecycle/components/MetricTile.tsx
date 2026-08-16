import { cn } from '@/lib/cn';

export interface MetricTileProps { label: string; value: string; detail?: string; className?: string; }

export function MetricTile({ label, value, detail, className }: MetricTileProps) {
  return (
    <article className={cn('rounded-xl border border-border bg-surface p-4 shadow-panel', className)}>
      <p className="text-caption font-medium text-muted">{label}</p>
      <p className="mt-2 font-display text-heading-2 text-ink">{value}</p>
      {detail ? <p className="mt-1 text-caption text-muted">{detail}</p> : null}
    </article>
  );
}
