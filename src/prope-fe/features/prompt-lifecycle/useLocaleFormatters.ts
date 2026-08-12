import { useTranslation } from 'react-i18next';

export function useLocaleFormatters() {
  const { i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language;
  return {
    date: (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)),
    /**
     * Money, from the decimal **string** the API sends.
     *
     * Costs are `Numeric(20, 10)` on the server and travel as strings for that
     * reason (A-107) — a JSON number would round them through a double on the way
     * here, quietly and in the direction of looking cheaper. `Number()` at the
     * point of display is where that rounding is acceptable, because it is the
     * last thing that happens to the value.
     *
     * `null` and `undefined` render as an em dash rather than as `$0.000`. An
     * unpriced call is one no price row covered yet, and printing zero for it
     * would be a number somebody sums.
     *
     * The currency is a parameter because a workspace prices in its own —
     * A-107 forbids conversion, so there is no house currency to default to.
     */
    currency: (value: string | number | null | undefined, currency = 'USD') => {
      if (value === null || value === undefined || value === '') return '—';
      const amount = typeof value === 'number' ? value : Number(value);
      if (!Number.isFinite(amount)) return '—';
      return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: 3 }).format(amount);
    },
    number: (value: number) => new Intl.NumberFormat(locale).format(value),
    percent: (value: number) => new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 1 }).format(value),
  };
}
