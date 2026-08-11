import { useCallback, useState, type KeyboardEvent, type PointerEvent } from 'react';

const MIN_WIDTH = 280;
const MAX_WIDTH = 480;
const DEFAULT_WIDTH = 320;
const KEYBOARD_STEP = 16;

function clamp(value: number) { return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, value)); }

export function useResizableNavigation() {
  const [width, setWidth] = useState(() => {
    const stored = Number.parseFloat(localStorage.getItem('prope-navigation-width') ?? '');
    return Number.isFinite(stored) ? clamp(stored) : DEFAULT_WIDTH;
  });
  const commit = useCallback((next: number) => {
    const clamped = clamp(next);
    setWidth(clamped);
    localStorage.setItem('prope-navigation-width', String(clamped));
  }, []);
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const origin = event.clientX;
    const initial = width;
    const move = (moveEvent: globalThis.PointerEvent) => setWidth(clamp(initial + moveEvent.clientX - origin));
    const up = (upEvent: globalThis.PointerEvent) => {
      event.currentTarget.releasePointerCapture(upEvent.pointerId);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      commit(initial + upEvent.clientX - origin);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    commit(width + (event.key === 'ArrowRight' ? KEYBOARD_STEP : -KEYBOARD_STEP));
  };
  return { width, minWidth: MIN_WIDTH, maxWidth: MAX_WIDTH, onPointerDown, onKeyDown };
}
