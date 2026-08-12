import { useRef, type KeyboardEvent } from 'react';

export function useRovingTabs(values: string[], activeValue: string, onValueChange: (value: string) => void) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = Math.max(0, values.indexOf(activeValue));
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? values.length - 1 : event.key === 'ArrowRight' ? (currentIndex + 1) % values.length : (currentIndex - 1 + values.length) % values.length;
    const value = values[nextIndex];
    if (!value) return;
    onValueChange(value);
    refs.current.get(value)?.focus();
  };
  const setRef = (value: string) => (node: HTMLButtonElement | null) => { if (node) refs.current.set(value, node); else refs.current.delete(value); };
  return { onKeyDown, setRef, refs };
}
