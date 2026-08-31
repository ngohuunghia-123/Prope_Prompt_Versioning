import { ArrowRight, Warning } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import type { RouterComboEntry } from '@/features/prompt-lifecycle/routerComboTypes';
import { providerConfigsOptions } from '@/features/prompt-lifecycle/queries';
import { cn } from '@/lib/cn';

/**
 * One combo's rungs, in order, on one line — ADR-0069.
 *
 * `1. OpenAI · gpt-4o-mini → 2. Azure · gpt-4o`. The combo's name tells an
 * author nothing about what they are choosing, so every place a combo is named
 * renders this beside it: the settings card, the composer's select, the review
 * screen and the frozen snapshot on a revision.
 *
 * The provider *name* is resolved here rather than on the wire. `RouterComboEntryRead`
 * carries an id and no display name, because resolving one server-side would put
 * registry SQL across a schema boundary into `provider.provider_config` — and
 * the client is already holding the provider list for its own binding fields.
 * A `prv_` id that no longer resolves renders as the id, which is the honest
 * answer for a provider somebody deleted.
 */
export function RouterComboSummary({ entries, warnUnusable = true, className }: {
  entries: readonly RouterComboEntry[];
  /**
   * Whether a rung pointing at a disabled or unverified provider gets a
   * warning. On a **frozen** snapshot it does not: that revision has already
   * been approved against those rungs, and a badge saying otherwise invites
   * somebody to "fix" a record that is not supposed to change.
   */
  warnUnusable?: boolean;
  className?: string;
}) {
  const { t } = useTranslation();
  const configs = useQuery(providerConfigsOptions);
  const providers = configs.data ?? [];

  if (entries.length === 0) return null;

  return (
    <ol className={cn('flex flex-wrap items-center gap-x-2 gap-y-1 text-caption', className)}>
      {entries.map((entry, index) => {
        const provider = providers.find((candidate) => candidate.provider_config_id === entry.provider_config_id);
        const unusable = warnUnusable
          && provider !== undefined
          && (provider.status === 'disabled' || provider.verification_status !== 'passed');
        return (
          <li key={`${entry.priority}-${entry.provider_config_id}-${entry.upstream_model}`} className="flex items-center gap-2">
            {index > 0 ? <ArrowRight aria-hidden className="size-3 shrink-0 text-muted" /> : null}
            <span className="flex items-center gap-1.5">
              <span className="text-muted">{t('lifecycle.router.priority', { rank: entry.priority })}</span>
              <span className={cn('font-medium text-ink', unusable && 'text-warning-text')}>
                {provider?.display_name ?? entry.provider_config_id}
              </span>
              <span aria-hidden className="text-muted">·</span>
              <span className="font-mono text-ink">{entry.upstream_model}</span>
              {unusable ? (
                <Warning
                  aria-label={t('lifecycle.router.card.unusableEntry', { name: provider?.display_name ?? entry.provider_config_id })}
                  className="size-3.5 shrink-0 text-warning-text"
                />
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
