import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface CardProps extends HTMLAttributes<HTMLElement> { title?: string; children: ReactNode; }

export function Card({ title, children, className, ...props }: CardProps) {
  return (
    <article className={cn('flex min-h-40 flex-col gap-2 rounded-modal border border-border bg-surface p-5 text-ink shadow-panel sm:p-6', className)} {...props}>
      {title ? <h3 className="font-display text-heading-3 font-normal">{title}</h3> : null}
      <div className="text-body text-muted">{children}</div>
    </article>
  );
}
