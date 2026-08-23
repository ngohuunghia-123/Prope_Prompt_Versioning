import { useTranslation } from 'react-i18next';
import { Fire } from '@phosphor-icons/react';

import { Tag } from '@/components/Tag';
import type { Release } from '@/features/prompt-lifecycle/releaseTypes';
import { useInsightsFormat } from '@/features/prompt-lifecycle/useInsightsFormat';

interface ReleaseHistoryTableProps {
  releases: Release[];
  /** `version_id` → the rail's own revision label, so a row names what the rail names. */
  revisionLabels: Record<string, string>;
}

/**
 * Every release decision on this prompt, newest first.
 *
 * **A withdrawal is a row, not an absence.** It carries a null `version_id` and
 * a required reason, which is the whole point: unpublishing is a recorded act
 * with a name against it, and history rows are never deleted.
 */
export function ReleaseHistoryTable({ releases, revisionLabels }: ReleaseHistoryTableProps) {
  const { t } = useTranslation();
  const format = useInsightsFormat();

  return (
    <section className="p-4 sm:p-6" aria-labelledby="release-history-title">
      <h2 id="release-history-title" className="font-display text-heading-3 text-ink">
        {t('lifecycle.release.historyTitle')}
      </h2>

      {releases.length === 0 ? (
        <p className="mt-3 text-body text-muted">{t('lifecycle.release.historyEmpty')}</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-180 border-collapse text-left text-body">
            <thead>
              <tr className="border-b border-border text-caption text-muted">
                <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.when')}</th>
                <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.action')}</th>
                <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.revision')}</th>
                <th scope="col" className="py-2 pr-4 font-normal">{t('lifecycle.release.columns.by')}</th>
                <th scope="col" className="py-2 font-normal">{t('lifecycle.release.columns.reason')}</th>
              </tr>
            </thead>
            <tbody>
              {releases.map((release) => (
                <tr key={release.release_id} className="border-b border-border/60 last:border-0 align-top">
                  <td className="py-2.5 pr-4 whitespace-nowrap text-muted">{format.dateTime(release.released_at)}</td>
                  <td className="py-2.5 pr-4">
                    <span className="flex items-center gap-2">
                      <Tag state={release.kind === 'withdraw' ? 'danger' : 'neutral'}>
                        {t(`lifecycle.release.kinds.${release.kind}`)}
                      </Tag>
                      {release.break_glass ? (
                        <span className="flex items-center gap-1 text-caption text-warning-strong">
                          <Fire aria-hidden className="size-3.5" />
                          {t('lifecycle.release.breakGlassTag')}
                        </span>
                      ) : null}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-ink">
                    {release.version_id
                      ? revisionLabels[release.version_id] ?? release.version_id
                      : t('lifecycle.release.nothingReleased')}
                  </td>
                  <td className="py-2.5 pr-4 text-muted">{release.released_by}</td>
                  <td className="py-2.5 max-w-96 text-muted">{release.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
