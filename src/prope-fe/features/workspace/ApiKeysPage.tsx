import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Notification } from '@/components/Notification';
import { useAgentSurface } from '@/features/chat/AgentSurfaceContext';
import { sessionOptions } from '@/features/auth/queries';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { ApiKeysPanel } from '@/features/workspace/ApiKeysPanel';
import { CodeSnippetsPanel } from '@/features/workspace/CodeSnippetsPanel';
import { INTERNAL_APP_LABEL } from '@/features/workspace/keyTypes';

/**
 * Per-app API keys, and the code that uses them.
 *
 * **Its own destination, not a corner of the playground.** Minting a key for a
 * second platform is a workspace decision taken with no prompt in hand, and
 * trying a draft is a prompt decision taken with no key in hand — putting them on
 * one screen made each one clutter for the other. What belongs together is the
 * key and the snippet: a snippet *is* a key plus a model name.
 *
 * **The playground and eval runs never appear here, because they hold no
 * credential.** They are attributed by the ledger's `source` column and their
 * rows carry a null `consumer_key_id`, refused otherwise by
 * `ck_call_record_playground_calls_are_internal`. So `{INTERNAL_APP_LABEL}` is a
 * bucket in a usage report and not a key: it cannot be minted, copied, revoked,
 * or used from outside, and no key on this page is needed to run a trial.
 */
export function ApiKeysPage() {
  const { t } = useTranslation();
  const { highlight } = useAgentSurface();
  const sessionQuery = useQuery(sessionOptions);

  if (sessionQuery.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (sessionQuery.isError) {
    return <QueryState state="error" onRetry={() => void sessionQuery.refetch()} />;
  }

  const workspaceId = sessionQuery.data?.user.workspaceId ?? '';

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6">
      <PageIntro
        eyebrow={t('keys.page.eyebrow')}
        title={t('keys.page.title')}
        description={t('keys.page.description')}
      />

      <Notification tone="info" title={t('keys.page.internalTitle', { internal: INTERNAL_APP_LABEL })}>
        {t('keys.page.internalBody', { internal: INTERNAL_APP_LABEL })}
      </Notification>

      <div
        className={
          highlight === 'keys-list'
            ? 'rounded-modal ring-2 ring-secondary ring-offset-2 ring-offset-canvas'
            : undefined
        }
      >
        <ApiKeysPanel />
      </div>
      <CodeSnippetsPanel workspaceId={workspaceId} />
    </div>
  );
}
