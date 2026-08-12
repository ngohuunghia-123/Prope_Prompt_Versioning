import { useCallback, useState, type KeyboardEvent, type PointerEvent } from 'react';

const MIN_WIDTH = 350;
const MAX_WIDTH = 640;
const DEFAULT_WIDTH = 399;
const MAGNETIC_THRESHOLD = 320;
const KEYBOARD_STEP = 16;

function clamp(value: number) { return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, value)); }

export function useResizableNavigation(collapsed: boolean, onCollapsedChange: (collapsed: boolean) => void) {
  const [width, setWidth] = useState(() => {
    const stored = Number.parseFloat(localStorage.getItem('prope-navigation-expanded-width') ?? '');
    return Number.isFinite(stored) ? clamp(stored) : DEFAULT_WIDTH;
  });
  const [isResizing, setIsResizing] = useState(false);
  const [isMagnetic, setIsMagnetic] = useState(false);
  const commit = useCallback((next: number) => {
    const clamped = clamp(next);
    setWidth(clamped);
    localStorage.setItem('prope-navigation-expanded-width', String(clamped));
  }, []);
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (collapsed) return;
    const handle = event.currentTarget;
    const pointerId = event.pointerId;
    handle.setPointerCapture(pointerId);
    const origin = event.clientX;
    const initial = width;
    let latestCandidate = initial;
    setIsResizing(true);
    const move = (moveEvent: globalThis.PointerEvent) => {
      latestCandidate = initial + moveEvent.clientX - origin;
      setIsMagnetic(latestCandidate < MIN_WIDTH);
      setWidth(clamp(latestCandidate));
    };
    const cleanup = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', cancel);
      if (handle.hasPointerCapture(pointerId)) handle.releasePointerCapture(pointerId);
      setIsResizing(false);
      setIsMagnetic(false);
    };
    const up = () => {
      cleanup();
      if (latestCandidate < MAGNETIC_THRESHOLD) {
        setWidth(initial);
        onCollapsedChange(true);
      }
      else {
        commit(latestCandidate);
        onCollapsedChange(false);
      }
    };
    const cancel = () => { cleanup(); setWidth(initial); };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', cancel);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 40 : KEYBOARD_STEP;
    if (event.key === 'Home') { event.preventDefault(); onCollapsedChange(true); return; }
    if (event.key === 'End') { event.preventDefault(); onCollapsedChange(false); commit(MAX_WIDTH); return; }
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    if (event.key === 'ArrowRight' && collapsed) { onCollapsedChange(false); return; }
    if (event.key === 'ArrowLeft' && width - step < MIN_WIDTH) { onCollapsedChange(true); return; }
    commit(width + (event.key === 'ArrowRight' ? step : -step));
  };
  return { width, minWidth: MIN_WIDTH, maxWidth: MAX_WIDTH, isResizing, isMagnetic, onPointerDown, onKeyDown };
}
