import { useTranslation } from 'react-i18next';

import type { UsageCost } from '@/features/prompt-lifecycle/insightsTypes';

/**
 * Formatting for figures that came out of the ledger.
 *
 * **Separate from `useLocaleFormatters` because that one hardcodes USD.** Every
 * `currency*` helper there passes `currency: 'USD'`, which is right for the mock
 * fixtures it was written for and wrong for a workspace whose provider is priced
 * in VND: it would render `₫12,000` as `$12,000.000`. Rather than widen a helper
 * a dozen screens depend on, the reads that carry their own currency code use
 * this.
 */
export function useInsightsFormat() {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language;

  const number = (value: number) => new Intl.NumberFormat(locale).format(value);

  /**
   * One amount in its own currency.
   *
   * The `try` is not superstition: `Intl.NumberFormat` throws `RangeError` on a
   * currency code it does not know, and the code here came from a price row
   * somebody typed. A provider registered with a made-up code should render as a
   * plain number beside that code, not take the tab down.
   */
  const money = (amount: number, currency: string) => {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        // Ledger costs are routinely fractions of a cent. Two decimals would
        // render most real per-call figures as 0.00, which reads as free.
        maximumFractionDigits: 6,
      }).format(amount);
    } catch {
      return `${number(amount)} ${currency}`;
    }
  };

  /**
   * A bucket's whole cost. One entry per currency, joined — never summed.
   *
   * An empty list is not zero. It means nothing in the bucket could be priced,
   * and the caller should be showing the unpriced count instead.
   */
  const costs = (entries: readonly UsageCost[]) =>
    entries.length === 0 ? null : entries.map((entry) => money(entry.amount, entry.currency)).join(' · ');

  /**
   * One call's cost, qualified by whether anybody could price it.
   *
   * `unpriced` returns a label rather than `0`: the tokens were spent, and a
   * zero in this column is a number somebody would add up.
   */
  const callCost = (amount: number | null, currency: string | null, status: string) => {
    if (status === 'unpriced') return t('lifecycle.insights.unpriced');
    if (status === 'not_applicable' || amount === null || currency === null) return '—';
    return money(amount, currency);
  };

  const percent = (value: number) =>
    new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 1 }).format(value);

  const dateTime = (value: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

  /** Milliseconds under a second stay milliseconds; a reader thinks in both. */
  const duration = (ms: number | null) => {
    if (ms === null) return '—';
    return ms < 1000 ? `${number(ms)} ms` : `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(ms / 1000)} s`;
  };

  return { number, money, costs, callCost, percent, dateTime, duration };
}
