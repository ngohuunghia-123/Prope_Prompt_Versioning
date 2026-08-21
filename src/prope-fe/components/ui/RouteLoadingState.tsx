import { useEffect, useState } from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';

export type RouteLoadingKind = 'redirect' | 'auth' | 'form' | 'workspace' | 'app';

export interface RouteLoadingStateProps {
  label: string;
  kind?: RouteLoadingKind;
  className?: string;
}

function AuthLoadingLayout() {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <Skeleton className="hidden min-h-dvh rounded-none lg:block" />
      <div className="grid place-items-center px-4 py-8 sm:px-8">
        <div className="grid w-full max-w-auth gap-7">
          <Skeleton variant="line" className="mx-auto w-28" />
          <Skeleton variant="line" className="mx-auto w-3/4" />
          <div className="grid gap-5"><Skeleton variant="control" /><Skeleton variant="control" /><Skeleton variant="control" /></div>
        </div>
      </div>
    </div>
  );
}

function FormLoadingLayout() {
  return (
    <div className="grid min-h-dvh place-items-center px-4 py-12 sm:px-8">
      <div className="grid w-full max-w-auth gap-6 rounded-visual border border-border bg-surface p-6 shadow-floating sm:p-8">
        <Skeleton variant="circle" />
        <Skeleton variant="line" className="w-2/3" />
        <Skeleton variant="line" className="w-full" />
        <div className="grid gap-4"><Skeleton variant="control" /><Skeleton variant="control" /><Skeleton variant="control" /></div>
      </div>
    </div>
  );
}

function WorkspaceLoadingLayout() {
  return (
    <div className="mx-auto grid min-h-dvh w-full max-w-3xl content-start gap-6 px-4 py-10">
      <div className="grid gap-3"><Skeleton variant="line" className="w-1/4" /><Skeleton variant="line" className="w-1/2" /><Skeleton variant="line" className="w-3/4" /></div>
      <Skeleton className="min-h-48" />
      <div className="grid gap-6 md:grid-cols-2"><Skeleton className="min-h-64" /><Skeleton className="min-h-64" /></div>
    </div>
  );
}

function AppLoadingLayout() {
  return <div className="grid min-h-dvh content-start gap-6 p-4 sm:p-6 lg:p-8"><Skeleton variant="line" className="w-1/3" /><Skeleton className="min-h-56" /></div>;
}

export function RouteLoadingState({ label, kind = 'redirect', className }: RouteLoadingStateProps) {
  const [showLayout, setShowLayout] = useState(false);

  useEffect(() => {
    if (kind === 'redirect') return;
    const timer = window.setTimeout(() => setShowLayout(true), 180);
    return () => window.clearTimeout(timer);
  }, [kind]);

  return (
    <div role="status" aria-busy="true" className={cn('min-h-dvh bg-canvas', className)}>
      <span className="sr-only">{label}</span>
      {showLayout && kind === 'auth' ? <AuthLoadingLayout /> : null}
      {showLayout && kind === 'form' ? <FormLoadingLayout /> : null}
      {showLayout && kind === 'workspace' ? <WorkspaceLoadingLayout /> : null}
      {showLayout && kind === 'app' ? <AppLoadingLayout /> : null}
    </div>
  );
}
