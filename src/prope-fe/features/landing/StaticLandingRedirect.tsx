import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';

export function StaticLandingRedirect() {
  const { t } = useTranslation();

  useEffect(() => {
    window.location.replace('/landing-page.html');
  }, []);

  return <ContentSkeleton label={t('common.loading')} layout="page" className="min-h-dvh bg-canvas p-6 lg:p-8" />;
}
