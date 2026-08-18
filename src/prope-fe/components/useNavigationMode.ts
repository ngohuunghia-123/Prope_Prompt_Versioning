import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import type { NavigationMode } from '@/components/navigationTypes';

const modes: NavigationMode[] = ['home', 'chat', 'notifications', 'search'];

function modeFromHash(hash: string): NavigationMode {
  const segment = hash.replace(/^#\/?/, '').split('/')[0];
  return modes.find((mode) => mode === segment) ?? 'home';
}

export function useNavigationMode() {
  const { hash } = useLocation();
  const [mode, setModeState] = useState<NavigationMode>(() => modeFromHash(hash));

  useEffect(() => {
    setModeState(modeFromHash(hash));
  }, [hash]);

  const setMode = useCallback((nextMode: NavigationMode) => {
    setModeState(nextMode);
    if (window.location.hash !== `#${nextMode}`) window.history.pushState({ mode: nextMode }, '', `#${nextMode}`);
  }, []);

  return { mode, setMode };
}
