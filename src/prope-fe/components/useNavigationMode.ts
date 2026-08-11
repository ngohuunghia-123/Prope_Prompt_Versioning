import { useCallback, useEffect, useState } from 'react';
import type { NavigationMode } from '@/components/navigationTypes';

const modes: NavigationMode[] = ['home', 'chat', 'notifications', 'search'];

function modeFromLocation(): NavigationMode {
  const segment = window.location.hash.replace(/^#\/?/, '').split('/')[0];
  return modes.find((mode) => mode === segment) ?? 'home';
}

export function useNavigationMode() {
  const [mode, setModeState] = useState<NavigationMode>(modeFromLocation);

  useEffect(() => {
    const syncMode = () => setModeState(modeFromLocation());
    window.addEventListener('hashchange', syncMode);
    window.addEventListener('popstate', syncMode);
    return () => {
      window.removeEventListener('hashchange', syncMode);
      window.removeEventListener('popstate', syncMode);
    };
  }, []);

  const setMode = useCallback((nextMode: NavigationMode) => {
    setModeState(nextMode);
    if (window.location.hash !== `#${nextMode}`) window.history.pushState({ mode: nextMode }, '', `#${nextMode}`);
  }, []);

  return { mode, setMode };
}
