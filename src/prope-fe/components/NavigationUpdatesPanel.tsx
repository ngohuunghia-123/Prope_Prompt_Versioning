import { useTranslation } from 'react-i18next';
import { navigationUpdateGroups } from '@/components/navigationData';

export function NavigationUpdatesPanel() {
  const { t, i18n } = useTranslation();
  const timeFormatter = new Intl.DateTimeFormat(i18n.language, { hour: 'numeric', minute: '2-digit' });
  return (
    <section aria-label={t('navigation.advanced.updates.label')} className="h-full animate-navigation-panel overflow-y-auto pb-2.5 pt-1.5 [scrollbar-color:var(--prope-color-border-default)_transparent] [scrollbar-width:thin]">
      {navigationUpdateGroups.map((group, groupIndex) => (
        <div key={group.labelKey} className={groupIndex === 0 ? 'grid gap-2.5' : 'mt-5 grid gap-2.5'}>
          <p className="m-0 text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t(`navigation.advanced.relative.${group.labelKey}`)}</p>
          {group.items.map(({ id, icon: Icon, date, titleKey, bodyKey }, itemIndex) => (
            <article key={id} className={itemIndex === group.items.length - 1 ? 'grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-2' : 'grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-2 border-b border-border/60 pb-2.5'}>
              <span className="grid size-8 place-items-center rounded-full bg-surface/60 text-secondary"><Icon aria-hidden className="size-navigation-icon" /></span>
              <div className="min-w-0"><div className="flex items-baseline justify-between gap-3 max-navigation-small:grid max-navigation-small:gap-0.5"><strong className="text-caption text-link">{t(`navigation.advanced.updates.${titleKey}`)}</strong><time dateTime={date} className="shrink-0 text-overline font-bold tracking-navigation-time text-navigation-overline uppercase max-navigation-small:-order-1">{timeFormatter.format(new Date(date))}</time></div><p className="mb-0 mt-0.5 text-navigation-detail leading-normal text-muted">{t(`navigation.advanced.updates.${bodyKey}`)}</p></div>
            </article>
          ))}
        </div>
      ))}
    </section>
  );
}
