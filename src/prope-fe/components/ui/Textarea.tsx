import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, id, label, error, hint, disabled, ...props },
  ref,
) {
  const textareaId = id ?? props.name;
  const descriptionId = error ? `${textareaId}-error` : hint ? `${textareaId}-hint` : undefined;
  return (
    <label className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink" htmlFor={textareaId}>
      <span>{label}</span>
      <textarea
        ref={ref}
        id={textareaId}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={descriptionId}
        className={cn('min-h-32 w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:border-border-disabled disabled:bg-disabled disabled:text-disabled-text', error && 'border-danger-strong focus:border-danger-strong focus:ring-danger-strong/25', className)}
        {...props}
      />
      {error ? <span id={descriptionId} className="text-caption font-normal text-danger-text">{error}</span> : null}
      {!error && hint ? <span id={descriptionId} className="text-caption font-normal text-muted">{hint}</span> : null}
    </label>
  );
});
