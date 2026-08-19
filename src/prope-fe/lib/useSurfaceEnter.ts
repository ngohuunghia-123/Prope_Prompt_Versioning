import { useLayoutEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { enterSurface } from '@/lib/motion';

export function useSurfaceEnter<T extends HTMLElement = HTMLElement>(trigger?: string) {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const context = gsap.context(() => { if (ref.current) enterSurface(ref.current); }, ref);
    return () => context.revert();
  }, [trigger]);
  return ref;
}
