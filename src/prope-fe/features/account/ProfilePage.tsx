import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { ProfileForm } from '@/features/account/ProfileForm';
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
        <ProfileForm displayName={session.data.user.displayName} email={session.data.user.email} />
      </Card>
    </div>
  );
}
