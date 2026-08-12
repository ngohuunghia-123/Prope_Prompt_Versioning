import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface SegmentOption { value: string; label: string; icon?: ReactNode; disabled?: boolean; }
export interface SegmentedControlProps { label: string; name: string; options: SegmentOption[]; value: string; onValueChange: (value: string) => void; className?: string; }

export function SegmentedControl({ label, name, options, value, onValueChange, className }: SegmentedControlProps) {
  const activeIndex = Math.max(options.findIndex((option) => option.value === value), 0);
  return (
    <fieldset className={cn('relative flex w-full max-w-90 gap-1 rounded-full bg-subtle p-1 shadow-inset', className)}>
      <legend className="sr-only">{label}</legend>
      <span aria-hidden className="pointer-events-none absolute top-1 bottom-1 left-1 rounded-full bg-surface shadow-raised transition-transform duration-(--prope-motion-duration-base) ease-standard" style={{ width: `calc((100% - 0.5rem) / ${options.length})`, transform: `translateX(${activeIndex * 100}%)` }} />
      {options.map((option) => (
        <label key={option.value} className={cn('relative z-10 flex h-8.5 min-w-0 flex-1 cursor-pointer items-center justify-center rounded-full px-2.5 text-caption font-medium text-muted transition-colors has-focus-visible:outline-2 has-focus-visible:outline-focus', value === option.value && 'text-link', option.disabled && 'cursor-not-allowed text-disabled-text')}>
          <input className="sr-only" type="radio" name={name} value={option.value} checked={value === option.value} disabled={option.disabled} onChange={() => onValueChange(option.value)} />
          <span className="flex min-w-0 items-center justify-center gap-2">
            {option.icon ? <span aria-hidden className="shrink-0">{option.icon}</span> : null}
            <span className="truncate">{option.label}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
