import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

export function StaticLandingRedirect() {
  const { t } = useTranslation();

  useEffect(() => {
    window.location.replace('/landing-page.html');
  }, []);

  return <div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>;
}
