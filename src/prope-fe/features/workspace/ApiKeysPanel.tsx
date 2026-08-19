import { Check, Copy, Key, Plus, Trash, Warning } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { sessionOptions } from '@/features/auth/queries';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { promptsOptions } from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import {
  useCreateKeyMutation,
  useRevokeKeyMutation,
  workspaceKeysOptions,
} from '@/features/workspace/keyQueries';
import { keysAreLive } from '@/features/workspace/keysApi';
import { INTERNAL_APP_LABEL, maskedKey, type ApiKey } from '@/features/workspace/keyTypes';

/**
 * One key per app, so usage has somewhere to land.
 *
 * **A key's `name` is the app**, and that is the whole per-app model: the ledger
 * records `consumer_key_id` on every gateway call, so grouping spend by "which
 * platform" is grouping by the name somebody typed here. There is no separate
 * app entity, because a second table would be a second thing to keep in step
 * with the credential that actually authenticates.
 *
 * **Scope is a list of `namespace/name`, checked by exact membership and
 * default-deny.** A key with an empty scope resolves nothing, and the consumer
 * sees the same not-found an unknown model name gets — so a leaked key cannot be
 * used to enumerate the registry. That is why the form below asks which prompts
 * rather than offering an "all prompts" switch: there is no wildcard, on purpose.
 *
 * **`Internal` is not on this page and cannot be minted.** Playground trials and
 * eval runs are attributed by the ledger's `source` column, not by a credential,
 * which is what makes them impossible to use from outside.
 *
 * A panel rather than a page: it is one tab of the playground workbench, beside
 * the chat that spends and the snippets that consume. The three used to be a page
 * each, which meant the screen that hands out a credential was two navigations
 * away from the screen that needs one.
 */
export function ApiKeysPanel() {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const live = keysAreLive();

  const sessionQuery = useQuery(sessionOptions);
  const workspaceId = sessionQuery.data?.user.workspaceId ?? '';
  const keysQuery = useQuery({
    ...workspaceKeysOptions(workspaceId),
    enabled: live && workspaceId !== '',
  });
  const promptsQuery = useQuery(promptsOptions);

  const createKey = useCreateKeyMutation(workspaceId);
  const revokeKey = useRevokeKeyMutation(workspaceId);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [scope, setScope] = useState<string[]>([]);
  const [secret, setSecret] = useState<{ name: string; value: string }>();
  const [pendingRevoke, setPendingRevoke] = useState<ApiKey>();
  const [copied, setCopied] = useState(false);

  if (sessionQuery.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (sessionQuery.isError) {
    return <QueryState state="error" onRetry={() => void sessionQuery.refetch()} />;
  }

  const modelNames = (promptsQuery.data ?? []).map((prompt) => prompt.modelName);
  const keys = keysQuery.data ?? [];

  function closeCreate() {
    setCreating(false);
    setName('');
    setScope([]);
  }

  async function copySecret(value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="grid gap-4">
      {!live ? (
        <Notification tone="info" title={t('keys.page.unavailable')}>
          {t('keys.page.unavailableHint')}
        </Notification>
      ) : null}

      {/* The one place the plaintext ever appears. Rendered as a panel rather
          than a toast because a toast that disappears takes an unrecoverable
          secret with it. */}
      {secret ? (
        <Card title={t('keys.created.title', { name: secret.name })}>
          <div className="grid gap-2 rounded-modal border border-warning-strong bg-warning/10 p-4">
            <div className="flex items-start gap-2">
              <Warning aria-hidden weight="fill" className="mt-0.5 size-4 shrink-0 text-warning-text" />
              <p className="text-caption font-medium text-warning-text">{t('keys.created.once')}</p>
            </div>
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-ink px-3 py-2 font-mono text-caption text-inverse">
                {secret.value}
              </code>
              <Button
                type="button"
                intent="neutral"
                size="small"
                leadingIcon={
                  copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />
                }
                onClick={() => void copySecret(secret.value)}
              >
                {t(copied ? 'keys.created.copied' : 'keys.created.copy')}
              </Button>
            </div>
          </div>
          <div className="justify-self-end">
            <Button type="button" intent="ghost" size="small" onClick={() => setSecret(undefined)}>
              {t('keys.created.dismiss')}
            </Button>
          </div>
        </Card>
      ) : null}

      <Card
        title={t('keys.list.title')}
        description={t('keys.list.description', { internal: INTERNAL_APP_LABEL })}
        action={
          <Button
            type="button"
            size="small"
            disabled={!live}
            leadingIcon={<Plus aria-hidden className="size-4" />}
            onClick={() => setCreating(true)}
          >
            {t('keys.list.create')}
          </Button>
        }
      >
        {revokeKey.isError ? (
          <Notification tone="error" title={t('keys.list.revokeError')}>
            {t('keys.list.revokeErrorHint')}
          </Notification>
        ) : null}

        {keysQuery.isPending && live ? (
          <ContentSkeleton label={t('common.loading')} layout="table" />
        ) : keysQuery.isError ? (
          <QueryState state="error" onRetry={() => void keysQuery.refetch()} />
        ) : keys.length === 0 ? (
          <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">
            {t('keys.list.empty')}
          </p>
        ) : (
          <ul className="grid gap-3">
            {keys.map((key) => (
              <li
                key={key.keyId}
                className="flex flex-wrap items-start justify-between gap-4 rounded-modal border border-border bg-subtle p-4"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface">
                    <Key className="size-5 text-primary" />
                  </span>
                  <div className="min-w-0 grid gap-1">
                    <p className="truncate text-body font-medium text-ink">{key.name}</p>
                    <code className="truncate font-mono text-caption text-muted">{maskedKey(key)}</code>
                    <p className="text-caption text-muted">
                      {key.scopeModelNames.length === 0
                        ? t('keys.list.scopeEmpty')
                        : t('keys.list.scopeCount', { count: key.scopeModelNames.length })}
                      {' · '}
                      {t('keys.list.created', { date: format.date(key.createdAt) })}
                      {' · '}
                      {key.lastUsedAt
                        ? t('keys.list.lastUsed', { date: format.date(key.lastUsedAt) })
                        : t('keys.list.neverUsed')}
                    </p>
                    {key.scopeModelNames.length > 0 ? (
                      <p className="truncate font-mono text-caption text-muted">
                        {key.scopeModelNames.join(', ')}
                      </p>
                    ) : null}
                  </div>
                </div>
                {key.revokedAt ? (
                  <span className="rounded-tag bg-disabled px-2 py-0.5 text-caption text-disabled-text">
                    {t('keys.list.revoked', { date: format.date(key.revokedAt) })}
                  </span>
                ) : (
                  <Button
                    type="button"
                    intent="danger"
                    size="small"
                    leadingIcon={<Trash aria-hidden className="size-4" />}
                    onClick={() => setPendingRevoke(key)}
                  >
                    {t('keys.list.revoke')}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal
        open={creating}
        title={t('keys.create.title')}
        description={t('keys.create.description')}
        confirmLabel={t('keys.create.confirm')}
        confirmLoading={createKey.isPending}
        confirmDisabled={name.trim() === ''}
        onClose={closeCreate}
        onConfirm={() =>
          createKey.mutate(
            { name: name.trim(), scopeModelNames: scope },
            {
              onSuccess: (created) => {
                setSecret({ name: created.name, value: created.secret });
                closeCreate();
              },
            },
          )
        }
      >
        <div className="grid gap-4">
          <Input
            label={t('keys.create.nameLabel')}
            hint={t('keys.create.nameHint')}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <fieldset className="grid gap-2">
            <legend className="text-body font-medium text-ink">{t('keys.create.scopeLabel')}</legend>
            <p className="text-caption text-muted">{t('keys.create.scopeHint')}</p>
            {modelNames.length === 0 ? (
              <p className="text-caption text-muted">{t('keys.create.noPrompts')}</p>
            ) : (
              <div className="grid max-h-56 gap-1 overflow-y-auto rounded-lg border border-border p-2">
                {modelNames.map((modelName) => (
                  <label
                    key={modelName}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-body font-normal text-ink hover:bg-subtle"
                  >
                    <input
                      type="checkbox"
                      checked={scope.includes(modelName)}
                      onChange={(event) =>
                        setScope((current) =>
                          event.target.checked
                            ? [...current, modelName]
                            : current.filter((item) => item !== modelName),
                        )
                      }
                      className="size-4 accent-primary"
                    />
                    <span className="truncate font-mono text-caption">{modelName}</span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>
        </div>
      </Modal>

      <Modal
        open={pendingRevoke !== undefined}
        destructive
        title={t('keys.revoke.title', { name: pendingRevoke?.name ?? '' })}
        description={t('keys.revoke.body')}
        confirmLabel={t('keys.list.revoke')}
        confirmLoading={revokeKey.isPending}
        onClose={() => setPendingRevoke(undefined)}
        onConfirm={() => {
          const target = pendingRevoke;
          if (!target) return;
          revokeKey.mutate(target.keyId, { onSuccess: () => setPendingRevoke(undefined) });
        }}
      />
    </div>
  );
}
