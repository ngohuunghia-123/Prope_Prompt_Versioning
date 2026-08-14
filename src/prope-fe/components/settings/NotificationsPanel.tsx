import { useTranslation } from 'react-i18next';
import { Bell, ChatCircle, CheckCircle, Warning } from '@phosphor-icons/react';
import { cn } from '@/lib/cn';

interface NotificationPreference {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}

export function NotificationsPanel() {
  const { t } = useTranslation();

  const preferences: NotificationPreference[] = [
    {
      id: 'reviewRequests',
      label: t('settings.notifications.reviewRequests.label'),
      description: t('settings.notifications.reviewRequests.description'),
      enabled: true,
      onChange: () => {},
    },
    {
      id: 'releaseDecisions',
      label: t('settings.notifications.releaseDecisions.label'),
      description: t('settings.notifications.releaseDecisions.description'),
      enabled: true,
      onChange: () => {},
    },
    {
      id: 'evaluationResults',
      label: t('settings.notifications.evaluationResults.label'),
      description: t('settings.notifications.evaluationResults.description'),
      enabled: true,
      onChange: () => {},
    },
    {
      id: 'promptUpdates',
      label: t('settings.notifications.promptUpdates.label'),
      description: t('settings.notifications.promptUpdates.description'),
      enabled: false,
      onChange: () => {},
    },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Bell aria-hidden className="size-5 text-secondary" />
          <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
            {t('settings.notifications.title')}
          </h3>
        </div>
        <p className="text-body text-muted">{t('settings.notifications.description')}</p>
      </div>

      <div className="space-y-3">
        {preferences.map((pref) => (
          <div
            key={pref.id}
            className="flex min-w-0 items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3"
          >
            <div className="min-w-0 flex-1">
              <p className="text-body font-medium text-ink">{pref.label}</p>
              <p className="text-caption text-muted">{pref.description}</p>
            </div>
            <button
              type="button"
              onClick={() => pref.onChange(!pref.enabled)}
              className={cn(
                'relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-focus',
                pref.enabled ? 'bg-primary' : 'bg-muted'
              )}
              role="switch"
              aria-checked={pref.enabled}
              aria-label={pref.label}
            >
              <span
                className={cn(
                  'inline-block size-4 rounded-full bg-white shadow-sm transition-transform duration-200',
                  pref.enabled ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
          {t('settings.notifications.deliveryChannel')}
        </h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5">
            <div className="flex items-center gap-3">
              <ChatCircle aria-hidden className="size-5 text-secondary" />
              <span className="text-body text-ink">{t('settings.notifications.inApp')}</span>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-caption text-primary">
              <CheckCircle aria-hidden className="size-3" weight="bold" />
              {t('settings.notifications.enabled')}
            </span>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5">
            <div className="flex items-center gap-3">
              <Bell aria-hidden className="size-5 text-secondary" />
              <span className="text-body text-ink">{t('settings.notifications.email')}</span>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-muted/30 px-2 py-0.5 text-caption text-muted">
              <Warning aria-hidden className="size-3" />
              {t('settings.notifications.comingSoon')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
