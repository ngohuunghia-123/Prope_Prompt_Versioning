import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPromptOpen } from '@/components/promptRecentOpensStorage';

export function usePromptOpenTracker() {
  const location = useLocation();

  useEffect(() => {
    const match = location.pathname.match(/^\/app\/prompts\/(.+)$/);
    if (!match) return;
    const id = match[1];
    if (!id || id.includes('/')) return;
    trackPromptOpen(id, document.title || id);
  }, [location.pathname]);
}
