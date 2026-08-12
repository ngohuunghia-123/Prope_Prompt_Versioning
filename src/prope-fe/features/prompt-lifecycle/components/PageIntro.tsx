import type { ReactNode } from 'react';

export interface PageIntroProps {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}

export function PageIntro({ eyebrow, title, description, action }: PageIntroProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        <p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{eyebrow}</p>
        <h2 className="mt-2 font-display text-heading-1 font-medium text-ink">{title}</h2>
        <p className="mt-2 text-body-large text-muted">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
