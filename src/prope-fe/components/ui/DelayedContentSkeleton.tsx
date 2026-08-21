import { useEffect, useState } from 'react';
import { ContentSkeleton, type ContentSkeletonLayout } from '@/components/ui/ContentSkeleton';
import { cn } from '@/lib/cn';

export interface DelayedContentSkeletonProps {
  label: string;
  layout?: ContentSkeletonLayout;
  className?: string;
  delay?: number;
}

export function DelayedContentSkeleton({ label, layout = 'page', className, delay = 180 }: DelayedContentSkeletonProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(timer);
  }, [delay]);

  return <ContentSkeleton label={label} layout={layout} className={cn(!visible && 'invisible', className)} />;
}
