import { ArrowLeft, ArrowRight } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { buttonVariants } from '@/components/ui/buttonVariants';
import { cn } from '@/lib/cn';

interface LifecycleLink {
  label: string;
  href: string;
}

export function LifecycleActionBar({ previous, next }: { previous?: LifecycleLink; next: LifecycleLink }) {
  return (
    <nav aria-label={next.label} className="sticky bottom-0 z-20 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
      {previous ? <Link to={previous.href} className={cn(buttonVariants({ intent: 'ghost', size: 'small' }))}><ArrowLeft aria-hidden className="size-4" /><span>{previous.label}</span></Link> : <span />}
      <Link to={next.href} className={cn(buttonVariants({ intent: 'primary', size: 'small' }))}><span>{next.label}</span><ArrowRight aria-hidden className="size-4" /></Link>
    </nav>
  );
}
