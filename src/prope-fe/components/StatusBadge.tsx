import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

const badgeVariants = cva('inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1.5 font-sans !text-caption font-normal shadow-tag before:size-2 before:rounded-full', {
  variants: {
    tone: {
      active: 'border-success-strong bg-success text-success-text before:bg-success-strong',
      pending: 'border-warning-strong bg-warning text-warning-strong before:bg-warning-strong',
      error: 'border-danger-strong bg-danger text-danger-text before:bg-danger-strong',
      disabled: 'border-border-disabled bg-disabled text-disabled-text before:bg-disabled-text',
    },
  },
  defaultVariants: { tone: 'active' },
});

export interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function StatusBadge({ className, tone, ...props }: StatusBadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
