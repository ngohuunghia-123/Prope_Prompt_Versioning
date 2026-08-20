import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode;
  description?: ReactNode;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(function Radio(
  { className, label, description, disabled, ...props }, ref,
) {
  return (
    <label className={cn('inline-flex min-h-5 cursor-pointer items-center gap-2 text-body text-ink', disabled && 'cursor-not-allowed text-disabled-text', className)}>
      <input ref={ref} type="radio" disabled={disabled} className="peer sr-only" {...props} />
      <span className="grid size-5 shrink-0 place-items-center rounded-full border border-border bg-surface shadow-inset transition-colors after:size-2.5 after:rounded-full after:bg-secondary after:opacity-0 peer-checked:border-secondary peer-checked:after:opacity-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus peer-disabled:border-border-disabled peer-disabled:bg-disabled" />
      <span className="min-w-0">
        <span className="block">{label}</span>
        {description ? <span className="mt-1 block text-caption font-normal text-muted">{description}</span> : null}
      </span>
    </label>
  );
});
