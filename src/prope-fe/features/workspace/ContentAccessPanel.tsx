import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Checkbox } from '@/components/ui/Checkbox';
import {
  contentAccessOptions,
  useSetContentAccessMutation,
} from '@/features/workspace/observabilityQueries';

interface ContentAccessPanelProps {
  workspaceId: string;
}

/**
 * The workspace's opt-in to reading retained request and response bodies.
 *
 * **Off is the default, and until this panel existed it was also the only
 * value.** The Log & Trace request panel asks the server for a redacted body,
 * the server checks this flag first, and a workspace that had never opted in
 * got `disabled` — correctly, and forever, because nothing in the SPA could set
 * it. The result read as a broken feature rather than as the deliberate
 * privacy default it is.
 *
 * **Turning it on is not the whole gate.** The reader still has to hold Owner,
 * Admin or Reviewer, bodies still expire on the retention window, and every
 * open is written to the audit log as `observability_content_viewed`. Said on
 * the screen rather than left in an ADR, because an Admin ticking this box is
 * making a privacy decision for everybody in the workspace and should be able
 * to see what it does before they make it.
 *
 * Admin-only, like the rest of this page: the routes behind it take
 * `spend_ceiling.manage`, which only Admin holds.
 */
export function ContentAccessPanel({ workspaceId }: ContentAccessPanelProps) {
  const { t } = useTranslation();
  const query = useQuery(contentAccessOptions(workspaceId));
  const setAccess = useSetContentAccessMutation(workspaceId);
  const enabled = query.data?.enabled ?? false;

  return (
    <Card title={t('members.contentAccess.title')}>
      <div className="grid gap-3">
        <p className="text-body text-muted">{t('members.contentAccess.description')}</p>
        <Checkbox
          label={t('members.contentAccess.label')}
          checked={enabled}
          disabled={query.isPending || setAccess.isPending}
          onChange={(event) => setAccess.mutate(event.target.checked)}
        />
        <p className="text-caption text-muted">{t('members.contentAccess.hint')}</p>
        {/* The write failing must not leave the box looking like it took: the
            checkbox renders from the query, which the mutation only updates on
            success, so the state on screen stays the state on the server. */}
        {setAccess.isError ? (
          <Notification tone="error" title={t('members.contentAccess.errorTitle')}>
            {t('members.contentAccess.error')}
          </Notification>
        ) : null}
        {query.isError ? (
          <Notification tone="error" title={t('members.contentAccess.errorTitle')}>
            {t('members.contentAccess.readError')}
          </Notification>
        ) : null}
      </div>
    </Card>
  );
}
