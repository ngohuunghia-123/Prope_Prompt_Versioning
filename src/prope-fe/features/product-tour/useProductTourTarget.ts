import { useEffect, useRef, useState } from 'react';

export interface ProductTourTargetRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

function visibleRect(element: HTMLElement): ProductTourTargetRect | null {
  const rect = element.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0 || element.getClientRects().length === 0) return null;
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
}

export function useProductTourTarget(targetId: string | undefined, ready: boolean, onMissing: () => void) {
  const [rect, setRect] = useState<ProductTourTargetRect | null>(null);
  const onMissingRef = useRef(onMissing);
  useEffect(() => { onMissingRef.current = onMissing; }, [onMissing]);

  useEffect(() => {
    setRect(null);
    if (!targetId || !ready) return;
    let element: HTMLElement | null = null;
    let resizeObserver: ResizeObserver | undefined;
    let frame = 0;
    let scrolled = false;

    const update = () => {
      frame = 0;
      if (!element?.isConnected) element = null;
      const next = element ? visibleRect(element) : null;
      if (next) setRect(next);
    };
    const scheduleUpdate = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    const find = () => {
      const candidate = document.querySelector<HTMLElement>(`[data-tour-id="${targetId}"]`);
      if (!candidate || !visibleRect(candidate)) return false;
      if (element !== candidate) {
        resizeObserver?.disconnect();
        element = candidate;
        resizeObserver = new ResizeObserver(scheduleUpdate);
        resizeObserver.observe(candidate);
      }
      if (!scrolled) {
        scrolled = true;
        candidate.scrollIntoView({ block: 'center', inline: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      }
      scheduleUpdate();
      return true;
    };

    const mutationObserver = new MutationObserver(() => { if (!find()) scheduleUpdate(); });
    mutationObserver.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style', 'data-tour-id'] });
    find();
    const timeout = window.setTimeout(() => { if (!element || !visibleRect(element)) onMissingRef.current(); }, 2_400);
    window.addEventListener('resize', scheduleUpdate);
    window.addEventListener('scroll', scheduleUpdate, true);
    return () => {
      window.clearTimeout(timeout);
      if (frame) cancelAnimationFrame(frame);
      mutationObserver.disconnect();
      resizeObserver?.disconnect();
      window.removeEventListener('resize', scheduleUpdate);
      window.removeEventListener('scroll', scheduleUpdate, true);
    };
  }, [ready, targetId]);

  return rect;
}
