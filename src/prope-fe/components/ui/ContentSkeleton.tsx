import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';

export type ContentSkeletonLayout = 'page' | 'table' | 'cards' | 'form' | 'inline';

export interface ContentSkeletonProps {
  label: string;
  layout?: ContentSkeletonLayout;
  className?: string;
}

function PageSkeleton() {
  return (
    <div className="grid gap-6">
      <div className="grid gap-3"><Skeleton variant="line" className="w-2/5 max-w-sm" /><Skeleton variant="line" className="w-4/5 max-w-xl" /></div>
      <Skeleton className="min-h-40" />
      <div className="grid gap-4 md:grid-cols-2"><Skeleton /><Skeleton /></div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="overflow-hidden rounded-modal border border-border bg-surface">
      <div className="grid grid-cols-3 gap-4 border-b border-border p-4"><Skeleton variant="line" /><Skeleton variant="line" /><Skeleton variant="line" /></div>
      {['one', 'two', 'three', 'four'].map((row) => (
        <div key={row} className="grid min-h-14 grid-cols-3 items-center gap-4 border-b border-border p-4 last:border-b-0">
          <Skeleton variant="line" className="w-4/5" /><Skeleton variant="line" className="w-3/5" /><Skeleton variant="line" className="w-2/5" />
        </div>
      ))}
    </div>
  );
}

function CardsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {['one', 'two', 'three', 'four', 'five', 'six'].map((card) => (
        <div key={card} className="grid min-h-40 gap-4 rounded-modal border border-border bg-surface p-5 shadow-panel">
          <div className="flex items-center gap-3"><Skeleton variant="circle" /><Skeleton variant="line" className="w-3/5" /></div>
          <Skeleton variant="line" className="w-full" /><Skeleton variant="line" className="w-2/3" />
        </div>
      ))}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="grid max-w-2xl gap-5 rounded-modal border border-border bg-surface p-6 shadow-panel">
      <Skeleton variant="line" className="w-2/5" />
      <div className="grid gap-2"><Skeleton variant="line" className="w-1/4" /><Skeleton variant="control" /></div>
      <div className="grid gap-2"><Skeleton variant="line" className="w-1/4" /><Skeleton className="min-h-32 rounded-lg" /></div>
      <Skeleton variant="control" className="w-32 justify-self-end" />
    </div>
  );
}

function InlineSkeleton() {
  return <div className="flex min-h-10 items-center gap-3"><Skeleton variant="circle" /><div className="grid flex-1 gap-2"><Skeleton variant="line" className="w-2/3" /><Skeleton variant="line" className="w-2/5" /></div></div>;
}

export function ContentSkeleton({ label, layout = 'page', className }: ContentSkeletonProps) {
  return (
    <div role="status" aria-busy="true" className={cn('min-w-0', className)}>
      <span className="sr-only">{label}</span>
      {layout === 'page' ? <PageSkeleton /> : null}
      {layout === 'table' ? <TableSkeleton /> : null}
      {layout === 'cards' ? <CardsSkeleton /> : null}
      {layout === 'form' ? <FormSkeleton /> : null}
      {layout === 'inline' ? <InlineSkeleton /> : null}
    </div>
  );
}
