import { Notification } from '@/components/Notification';
import { useTranslation } from 'react-i18next';

export interface EvalWorkspaceAlertsProps {
  offline: boolean;
  attachError: boolean;
  runError: boolean;
  draftError: boolean;
  /** Attached datasets but the revision binds no provider — running would fail. */
  needsProvider: boolean;
  onAddProvider: () => void;
  deleteNote?: { name: string; detached: number };
  onDismissDeleteNote: () => void;
}

/** Every condition the workspace wants to say out loud, in one stack.
 *
 * Order matters less than presence: each row is a fact about a different write
 * or guard, and stacking them keeps any one from being discovered only after
 * the button built on top of it failed. */
export function EvalWorkspaceAlerts({
  offline,
  attachError,
  runError,
  draftError,
  needsProvider,
  onAddProvider,
  deleteNote,
  onDismissDeleteNote,
}: EvalWorkspaceAlertsProps) {
  const { t } = useTranslation();
  return (
    <>
      {offline ? (
        <Notification tone="info" title={t('lifecycle.evalRun.unavailable')}>
          {t('lifecycle.evalRun.unavailableHint')}
        </Notification>
      ) : null}
      {attachError ? (
        <Notification tone="error" title={t('lifecycle.evalRun.attachError')}>
          {t('lifecycle.evalRun.attachErrorHint')}
        </Notification>
      ) : null}
      {runError ? (
        <Notification tone="error" title={t('lifecycle.evalRun.runError')}>
          {t('lifecycle.evalRun.runErrorHint')}
        </Notification>
      ) : null}
      {needsProvider ? (
        <Notification tone="warning" title={t('lifecycle.evalRun.needsProvider')}>
          <span>
            {t('lifecycle.evalRun.needsProviderHint')}{' '}
            <button type="button" className="cursor-pointer font-semibold text-link underline" onClick={onAddProvider}>
              {t('lifecycle.evalRun.addProvider')}
            </button>
          </span>
        </Notification>
      ) : null}
      {draftError ? (
        <Notification tone="error" title={t('lifecycle.evalDatasets.draftError')}>
          {t('lifecycle.evalDatasets.draftErrorHint')}
        </Notification>
      ) : null}
      {deleteNote ? (
        <Notification
          tone="info"
          title={t('lifecycle.evalDatasets.deleted', { name: deleteNote.name })}
          onDismiss={onDismissDeleteNote}
        >
          {deleteNote.detached > 0
            ? t('lifecycle.evalDatasets.deletedDetached', { count: deleteNote.detached })
            : t('lifecycle.evalDatasets.deletedClean')}
        </Notification>
      ) : null}
    </>
  );
}
