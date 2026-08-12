import { useTranslation } from 'react-i18next';

export function useLocaleFormatters() {
  const { i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language;
  return {
    date: (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)),
    currency: (value: number) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', minimumFractionDigits: 3 }).format(value),
    number: (value: number) => new Intl.NumberFormat(locale).format(value),
    percent: (value: number) => new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 1 }).format(value),
  };
}
