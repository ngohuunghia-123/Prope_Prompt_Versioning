import type { ReactNode } from 'react';
import { useSurfaceEnter } from '@/lib/useSurfaceEnter';

export interface ShowcaseSectionProps { id: string; title: string; children: ReactNode; }

export function ShowcaseSection({ id, title, children }: ShowcaseSectionProps) {
  const ref = useSurfaceEnter();
  return (
    <section ref={ref} id={id} className="space-y-5 scroll-mt-24">
      <div className="flex items-center gap-3"><span aria-hidden className="h-px w-8 bg-secondary" /><h2 className="text-heading-2 font-semibold">{title}</h2></div>
      {children}
    </section>
  );
}
