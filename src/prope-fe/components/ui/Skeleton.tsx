import type { HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';

const skeletonVariants = cva('skeleton-shimmer relative overflow-hidden bg-skeleton', {
  variants: {
    variant: {
      block: 'min-h-24 rounded-modal',
      line: 'h-4 rounded-full',
      circle: 'size-10 shrink-0 rounded-full',
      control: 'h-11 rounded-lg',
    },
  },
  defaultVariants: { variant: 'block' },
});

export interface SkeletonProps
  extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof skeletonVariants> {}

export function Skeleton({ variant, className, ...props }: SkeletonProps) {
  return (
    <div
      {...props}
      aria-hidden="true"
      className={cn(skeletonVariants({ variant }), className)}
    />
  );
}
