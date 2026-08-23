import { useLayoutEffect, useRef, type HTMLAttributes, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { animatePresence } from '@/lib/motion';

export interface MotionTableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  children: ReactNode;
}

export function MotionTableRow({ children, ...props }: MotionTableRowProps) {
  const ref = useRef<HTMLTableRowElement>(null);

  useLayoutEffect(() => {
    if (!ref.current) return;
    const context = gsap.context(() => {
      if (ref.current) animatePresence(ref.current, 'row', true);
    }, ref);
    return () => context.revert();
  }, []);

  return <tr ref={ref} {...props}>{children}</tr>;
}
