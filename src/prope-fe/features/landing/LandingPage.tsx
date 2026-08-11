import { useTranslation } from 'react-i18next';

export function LandingPage() {
  const { t } = useTranslation();

  return (
    <iframe
      title={t('common.propeHome')}
      src="/landing-page.html"
      className="block h-dvh w-full border-0"
    />
  );
}
