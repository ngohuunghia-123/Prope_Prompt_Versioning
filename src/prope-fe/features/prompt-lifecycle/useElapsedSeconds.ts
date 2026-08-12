import { useEffect, useState } from 'react';

export function useElapsedSeconds(startedAt?: string, running = false) {
  const [elapsed, setElapsed] = useState<number | undefined>(() => startedAt ? Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)) : undefined);
  useEffect(() => {
    if (!running || !startedAt) { setElapsed(undefined); return; }
    const update = () => setElapsed(Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [running, startedAt]);
  return elapsed;
}
