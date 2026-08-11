import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('prope-theme');
    return saved === 'dark' ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('prope-theme', theme);
    document.querySelector<HTMLLinkElement>('#prope-favicon')?.setAttribute('href', theme === 'dark' ? '/assets/prope-logo-inverse.svg' : '/assets/prope-mark.svg');
  }, [theme]);

  return { theme, setTheme };
}
