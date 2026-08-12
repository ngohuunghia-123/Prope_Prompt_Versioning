import { Check } from '@phosphor-icons/react';
import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, label, disabled, ...props }, ref,
) {
  return (
    <label className={cn('group inline-flex min-h-5 cursor-pointer items-center gap-2 text-body text-ink', disabled && 'cursor-not-allowed text-disabled-text', className)}>
      <input ref={ref} type="checkbox" disabled={disabled} className="peer sr-only" {...props} />
      <span className="grid size-5 shrink-0 place-items-center rounded border border-border bg-surface shadow-inset transition-colors peer-checked:border-secondary peer-checked:bg-secondary peer-checked:[&>svg]:opacity-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus peer-disabled:border-border-disabled peer-disabled:bg-disabled">
        <Check aria-hidden weight="bold" className="size-3.5 text-inverse opacity-0" />
      </span>
      <span>{label}</span>
    </label>
  );
});
