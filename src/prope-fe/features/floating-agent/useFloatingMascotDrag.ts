import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';

interface MascotPosition { x: number; y: number; }
const POSITION_KEY = 'prope-floating-agent-position';
const MASCOT_SIZE = 60;
const VIEWPORT_GUTTER = 16;
const DRAG_THRESHOLD = 4;

function defaultPosition(): MascotPosition {
  return { x: window.innerWidth - MASCOT_SIZE - 28, y: window.innerHeight - MASCOT_SIZE - 76 };
}

function clampPosition(position: MascotPosition): MascotPosition {
  return {
    x: Math.min(Math.max(position.x, VIEWPORT_GUTTER), window.innerWidth - MASCOT_SIZE - VIEWPORT_GUTTER),
    y: Math.min(Math.max(position.y, VIEWPORT_GUTTER), window.innerHeight - MASCOT_SIZE - 72),
  };
}

function readPosition() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(POSITION_KEY) ?? '') as Partial<MascotPosition>;
    if (typeof parsed.x === 'number' && typeof parsed.y === 'number') return clampPosition({ x: parsed.x, y: parsed.y });
  } catch { /* Invalid or unavailable stored position falls back safely. */ }
  return clampPosition(defaultPosition());
}

export function useFloatingMascotDrag() {
  const [position, setPosition] = useState(readPosition);
  const positionRef = useRef(position);
  const [dragging, setDragging] = useState(false);
  const origin = useRef<{ pointerX: number; pointerY: number; position: MascotPosition } | null>(null);
  const moved = useRef(false);

  useEffect(() => {
    const onResize = () => {
      const next = clampPosition(positionRef.current);
      positionRef.current = next;
      setPosition(next);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    origin.current = { pointerX: event.clientX, pointerY: event.clientY, position };
    moved.current = false;
  }, [position]);

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!origin.current) return;
    const deltaX = event.clientX - origin.current.pointerX;
    const deltaY = event.clientY - origin.current.pointerY;
    if (Math.hypot(deltaX, deltaY) >= DRAG_THRESHOLD) { moved.current = true; setDragging(true); }
    if (moved.current) {
      const next = clampPosition({ x: origin.current.position.x + deltaX, y: origin.current.position.y + deltaY });
      positionRef.current = next;
      setPosition(next);
    }
  }, []);

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!origin.current) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    origin.current = null;
    setDragging(false);
    if (moved.current) window.localStorage.setItem(POSITION_KEY, JSON.stringify(positionRef.current));
  }, []);

  const onPointerCancel = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    origin.current = null;
    moved.current = false;
    setDragging(false);
  }, []);

  return { position, dragging, moved, onPointerDown, onPointerMove, onPointerUp, onPointerCancel };
}
