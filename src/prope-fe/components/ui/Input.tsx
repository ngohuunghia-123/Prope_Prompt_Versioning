import { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  labelHidden?: boolean;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, id, label, labelHidden = false, error, hint, disabled, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const descriptionId = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  return (
    <label className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink" htmlFor={inputId}>
      <span className={labelHidden ? 'sr-only' : undefined}>{label}</span>
      <input
        ref={ref}
        id={inputId}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={descriptionId}
        className={cn(
          'h-11 w-full min-w-0 cursor-text rounded-lg border border-border bg-surface px-3 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:border-border-disabled disabled:bg-disabled disabled:text-disabled-text',
          error && 'border-danger-strong focus:border-danger-strong focus:ring-danger-strong/25',
          className,
        )}
        {...props}
      />
      {error ? <span id={descriptionId} className="text-caption font-normal text-danger-text">{error}</span> : null}
      {!error && hint ? <span id={descriptionId} className="text-caption font-normal text-muted">{hint}</span> : null}
    </label>
  );
});
