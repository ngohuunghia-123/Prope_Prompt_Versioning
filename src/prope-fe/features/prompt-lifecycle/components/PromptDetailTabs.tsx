import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

interface PromptDetailTabsProps { promptId: string; }

export function PromptDetailTabs({ promptId }: PromptDetailTabsProps) {
  const { t } = useTranslation();
  const items = [
    { label: t('lifecycle.overview.tabs.versioning'), to: `/app/prompts/${promptId}`, end: true },
    { label: t('lifecycle.overview.tabs.logs'), to: `/app/prompts/${promptId}/logs`, end: false },
    { label: t('lifecycle.overview.tabs.production'), to: `/app/prompts/${promptId}/production`, end: false },
    { label: t('lifecycle.overview.tabs.evaluation'), to: `/app/prompts/${promptId}/evaluation`, end: false },
  ];

  return (
    <nav aria-label={t('lifecycle.promptDetail.sectionNavigation')} className="flex min-h-14 items-end gap-1 overflow-x-auto border-b border-border bg-canvas px-4 sm:px-6">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => cn(
            'border-b-2 px-4 py-4 text-body font-semibold whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-focus',
            isActive ? 'border-secondary text-ink' : 'border-transparent text-muted hover:text-ink',
          )}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
