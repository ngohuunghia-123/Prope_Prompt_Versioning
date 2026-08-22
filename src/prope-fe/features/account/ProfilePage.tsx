import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { sessionOptions } from '@/features/auth/queries';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';

export function ProfilePage() {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);

  if (session.isPending) return <QueryState state="loading" />;
  if (session.isError) return <QueryState state="error" onRetry={() => void session.refetch()} />;
  if (!session.data) return <QueryState state="empty" />;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6">
      <PageIntro eyebrow={t('account.profile.eyebrow')} title={t('account.profile.title')} description={t('account.profile.description')} />
      <Card title={t('account.profile.cardTitle')} description={t('account.profile.cardDescription')}>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-control bg-subtle p-4">
            <dt className="text-caption font-medium text-muted">{t('account.profile.displayName')}</dt>
            <dd className="mt-1 text-body text-ink">{session.data.user.displayName}</dd>
          </div>
          <div className="rounded-control bg-subtle p-4">
            <dt className="text-caption font-medium text-muted">{t('account.profile.email')}</dt>
            <dd className="mt-1 break-all text-body text-ink">{session.data.user.email}</dd>
          </div>
        </dl>
        <p className="mt-4 text-body text-muted">{t('account.profile.readOnly')}</p>
      </Card>
    </div>
  );
}
