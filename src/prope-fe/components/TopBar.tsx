import { List, Moon, Sun } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import type { Theme } from '@/lib/useTheme';

export interface TopBarProps { title: string; description?: string; action?: ReactNode; theme: Theme; onThemeChange: (theme: Theme) => void; onOpenNavigation: () => void; }

export function TopBar({ title, description, action, theme, onThemeChange, onOpenNavigation }: TopBarProps) {
  const { t } = useTranslation();
  const nextTheme = theme === 'light' ? 'dark' : 'light';
  return (
    <header className="flex min-h-20 items-center gap-3 border-b border-border bg-canvas/90 px-4 py-3 backdrop-blur-sm sm:px-6">
      <button type="button" onClick={onOpenNavigation} aria-label={t('common.openNavigation')} className="grid size-10 shrink-0 place-items-center rounded-lg text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus lg:hidden">
        <List aria-hidden className="size-6" />
      </button>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-heading-3 font-medium text-ink sm:text-heading-2">{title}</h1>
        {description ? <p className="hidden truncate text-caption text-muted sm:block">{description}</p> : null}
      </div>
      <button type="button" onClick={() => onThemeChange(nextTheme)} aria-label={nextTheme === 'dark' ? t('common.dark') : t('common.light')} className="grid size-10 place-items-center rounded-lg text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
        {theme === 'light' ? <Moon aria-hidden className="size-5" /> : <Sun aria-hidden className="size-5" />}
      </button>
      {action ? <div>{action}</div> : null}
    </header>
  );
}
