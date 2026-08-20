import { BellSimple, ChatsTeardrop, House, MagnifyingGlass } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import type { NavigationMode } from '@/components/navigationTypes';
import { cn } from '@/lib/cn';

const modes = [
  { id: 'home', icon: House },
  { id: 'chat', icon: ChatsTeardrop },
  { id: 'notifications', icon: BellSimple },
  { id: 'search', icon: MagnifyingGlass },
] as const;

export interface NavigationModeTabsProps {
  mode: NavigationMode;
  compact?: boolean;
  onModeChange: (mode: NavigationMode) => void;
}

export function NavigationModeTabs({ mode, compact = false, onModeChange }: NavigationModeTabsProps) {
  const { t } = useTranslation();
  const activeIndex = modes.findIndex((item) => item.id === mode);
  if (compact) {
    return (
      <nav aria-label={t('navigation.advanced.primaryLabel')} className="relative flex flex-col gap-1 rounded-full bg-navigation-control p-1 shadow-inset">
        {modes.map(({ id, icon: Icon }) => (
          <button key={id} type="button" data-compact-mode={id} aria-label={t(`navigation.advanced.modes.${id}.label`)} title={t(`navigation.advanced.modes.${id}.label`)} onClick={() => onModeChange(id)} className="relative z-10 grid size-8 cursor-pointer place-items-center rounded-full bg-transparent text-navigation-icon transition-transform duration-(--prope-motion-duration-fast) hover:scale-105 focus-visible:outline-2 focus-visible:outline-focus">
            <Icon aria-hidden className="size-navigation-icon" />
          </button>
        ))}
      </nav>
    );
  }
  return (
    <nav aria-label={t('navigation.advanced.primaryLabel')} className="relative flex h-10.5 min-w-0 items-center gap-1 rounded-full bg-navigation-control p-1 shadow-inset">
      <span aria-hidden className="pointer-events-none absolute left-1 top-1 h-8.5 w-[calc((100%-1.25rem)/4)] rounded-full bg-surface shadow-raised transition-transform duration-(--prope-motion-duration-fast) ease-standard motion-reduce:transition-none" style={{ transform: `translateX(calc(${activeIndex} * (100% + 0.25rem)))` }} />
      {modes.map(({ id, icon: Icon }) => (
        <a key={id} href={`#${id}`} data-mode={id} aria-label={t(`navigation.advanced.modes.${id}.label`)} aria-current={mode === id ? 'page' : undefined} onClick={(event) => { event.preventDefault(); onModeChange(id); }} className={cn('relative z-10 inline-flex h-8.5 min-w-0 flex-1 items-center justify-center gap-1.5 overflow-hidden rounded-full px-2 text-caption font-medium whitespace-nowrap text-navigation-tab transition-colors duration-(--prope-motion-duration-fast) hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', mode === id && 'text-navigation-active')}>
          <Icon aria-hidden className="size-navigation-icon shrink-0" />
          <span className="min-w-0 truncate text-caption">{t(`navigation.advanced.modes.${id}.tab`)}</span>
        </a>
      ))}
    </nav>
  );
}
