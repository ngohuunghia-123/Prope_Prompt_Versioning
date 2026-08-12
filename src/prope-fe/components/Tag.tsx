import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

const tagVariants = cva('inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1.5 font-sans !text-caption font-normal shadow-tag', {
  variants: {
    state: {
      default: 'border-tag-info bg-tag-info-soft text-tag-info',
      neutral: 'border-border bg-subtle text-muted',
      warning: 'border-warning-strong bg-warning text-warning-strong',
      success: 'border-success-strong bg-success text-success-text',
      danger: 'border-danger-strong bg-danger text-danger-text',
    },
  },
  defaultVariants: { state: 'default' },
});

export interface TagProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof tagVariants> {}

export function Tag({ className, state, ...props }: TagProps) {
  return <span className={cn(tagVariants({ state }), className)} {...props} />;
}
