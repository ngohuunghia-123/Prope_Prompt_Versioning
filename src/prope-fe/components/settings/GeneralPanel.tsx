import { useTranslation } from 'react-i18next';
import { Globe, Moon, Bell } from '@phosphor-icons/react';
import { Select } from '@/components/ui/Select';

export function GeneralPanel() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.general.language')}
        </h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
            <Globe aria-hidden className="size-5 text-secondary" />
            <div className="min-w-0 flex-1">
              <p className="text-body font-medium text-ink">{t('settings.general.languageLabel')}</p>
              <p className="text-caption text-muted">{t('settings.general.languageDescription')}</p>
            </div>
          </div>
          <Select
            label=""
            value="vi"
            options={[
              { value: 'vi', label: 'Tiếng Việt' },
              { value: 'en', label: 'English' },
            ]}
            onValueChange={() => {}}
            className="w-full"
          />
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.general.theme')}
        </h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
            <Moon aria-hidden className="size-5 text-secondary" />
            <div className="min-w-0 flex-1">
              <p className="text-body font-medium text-ink">{t('settings.general.themeLabel')}</p>
              <p className="text-caption text-muted">{t('settings.general.themeDescription')}</p>
            </div>
          </div>
          <Select
            label=""
            value="system"
            options={[
              { value: 'system', label: t('settings.general.themeSystem') },
              { value: 'light', label: t('settings.general.themeLight') },
              { value: 'dark', label: t('settings.general.themeDark') },
            ]}
            onValueChange={() => {}}
            className="w-full"
          />
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.general.notifications')}
        </h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
            <Bell aria-hidden className="size-5 text-secondary" />
            <div className="min-w-0 flex-1">
              <p className="text-body font-medium text-ink">{t('settings.general.notificationsLabel')}</p>
              <p className="text-caption text-muted">{t('settings.general.notificationsDescription')}</p>
            </div>
          </div>
          <Select
            label=""
            value="all"
            options={[
              { value: 'all', label: t('settings.general.notificationsAll') },
              { value: 'important', label: t('settings.general.notificationsImportant') },
              { value: 'none', label: t('settings.general.notificationsNone') },
            ]}
            onValueChange={() => {}}
            className="w-full"
          />
        </div>
      </div>
    </div>
  );
}
