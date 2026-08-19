import { useLayoutEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { animateBackdrop, animatePresence, type MotionPreset } from '@/lib/motion';

export function useMotionPresence(visible: boolean, preset: MotionPreset) {
  const [mounted, setMounted] = useState(visible);
  const surfaceRef = useRef<HTMLElement>(null);
  const backdropRef = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    if (visible && !mounted) setMounted(true);
  }, [mounted, visible]);

  useLayoutEffect(() => {
    if (!mounted || !surfaceRef.current) return;
    const surface = surfaceRef.current;
    const backdrop = backdropRef.current;
    const context = gsap.context(() => {
      animatePresence(surface, preset, visible, visible ? undefined : () => setMounted(false));
      if (backdrop) animateBackdrop(backdrop, visible);
    });
    return () => context.revert();
  }, [mounted, preset, visible]);

  return { mounted, surfaceRef, backdropRef };
}
