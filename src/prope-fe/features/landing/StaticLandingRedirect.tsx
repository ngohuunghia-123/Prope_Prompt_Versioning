import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { RouteLoadingState } from '@/components/ui/RouteLoadingState';

export function StaticLandingRedirect() {
  const { t } = useTranslation();

  useEffect(() => {
    window.location.replace('/landing-page.html');
  }, []);

  return <RouteLoadingState label={t('common.loading')} kind="redirect" />;
}
