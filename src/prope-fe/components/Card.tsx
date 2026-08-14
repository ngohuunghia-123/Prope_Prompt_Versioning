import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface CardProps extends HTMLAttributes<HTMLElement> {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function Card({ title, description, action, children, className, ...props }: CardProps) {
  return (
    <article className={cn('flex min-h-40 flex-col gap-4 rounded-modal border border-border bg-surface p-5 text-ink shadow-panel sm:p-6', className)} {...props}>
      {title || description || action ? (
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            {title ? <h3 className="font-display text-heading-3 font-normal">{title}</h3> : null}
            {description ? <p className="mt-1 text-caption text-muted">{description}</p> : null}
          </div>
          {action}
        </header>
      ) : null}
      <div className="grid gap-4 text-body text-muted">{children}</div>
    </article>
  );
}
