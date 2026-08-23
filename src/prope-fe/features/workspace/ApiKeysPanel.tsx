import {
  Check,
  Copy,
  Eye,
  EyeSlash,
  FolderSimple,
  Key,
  Plus,
  SlidersHorizontal,
  Trash,
  Warning,
} from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { Select } from '@/components/ui/Select';
import { sessionOptions } from '@/features/auth/queries';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import {
  foldersOptions,
  promptsOptions,
  providerConfigsOptions,
} from '@/features/prompt-lifecycle/queries';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import {
  useCreateKeyMutation,
  useRevokeKeyMutation,
  useSetKeyScopeMutation,
  workspaceKeysOptions,
} from '@/features/workspace/keyQueries';
import { keysAreLive } from '@/features/workspace/keysApi';
import {
  INTERNAL_APP_LABEL,
  keyObserves,
  maskedKey,
  type ApiKey,
  type CreatedApiKey,
  type KeyScope,
} from '@/features/workspace/keyTypes';

/** The `Select` value that means "no provider chosen", matching the editor's. */
const UNSET = '__unset__';

/**
 * One key per app, so usage has somewhere to land.
 *
 * **A key's `name` is the app**, and that is the whole per-app model: the ledger
 * records `consumer_key_id` on every gateway call, so grouping spend by "which
 * platform" is grouping by the name somebody typed here. There is no separate
 * app entity, because a second table would be a second thing to keep in step
 * with the credential that actually authenticates.
 *
 * **Scope is folders first, prompts second, and the two are a union.** A-158:
 * one folder here replaces the thousand `namespace/name` entries a product that
 * owns one would otherwise be granted, and it keeps replacing them as the folder
 * grows — a key scoped to a folder needs no re-granting when a prompt is added
 * to it. The per-prompt list stays for the narrow case, and INT-004 resolves a
 * name that is in `scope_model_names` **or** whose namespace is in
 * `scope_namespaces`.
 *
 * **Still default-deny, and still no wildcard.** Both lists empty resolves
 * nothing — `= ANY('{}')` is false for every input, so there is no branch anybody
 * could forget — and the consumer sees the same not-found an unknown model name
 * gets, so a leaked key cannot be used to enumerate the registry. A folder is a
 * *bounded* grant, not "all prompts": there is deliberately no switch for that.
 *
 * **Observe mode is set here and only after minting.** `KeyCreate` has no
 * `observe_*` fields, so the pair travels on `PUT .../scope` — which is why this
 * panel has a scope dialog separate from the create dialog rather than one form
 * that does both. ADR-0059: a key that observes forwards a call the registry
 * cannot resolve to the named provider configuration and files what it saw under
 * the named namespace, instead of refusing it.
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
  const foldersQuery = useQuery(foldersOptions);
  const providersQuery = useQuery({ ...providerConfigsOptions, enabled: live });

  const createKey = useCreateKeyMutation(workspaceId);
  const revokeKey = useRevokeKeyMutation(workspaceId);
  const setScopeOf = useSetKeyScopeMutation(workspaceId);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [scope, setScope] = useState<string[]>([]);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  // The whole minted key, not just its secret. The panel below has to offer
  // "set up recording" on the key that was just created, and that needs its id
  // and its folders — which are not in the list query yet, because the list has
  // not refetched and the row does not exist to click.
  const [secret, setSecret] = useState<CreatedApiKey>();
  const [pendingRevoke, setPendingRevoke] = useState<ApiKey>();
  const [copied, setCopied] = useState(false);

  // The key whose reach is being edited, and the draft of that reach. Held as
  // one nullable object rather than an `editing` flag beside four fields, so the
  // dialog cannot open against a key that has since been revoked out from under
  // it — closing it clears the draft and the target together.
  const [editing, setEditing] = useState<{ key: ScopeTarget; draft: KeyScope }>();

  if (sessionQuery.isPending) return <QueryState state="loading" loadingLayout="table" />;
  if (sessionQuery.isError) {
    return <QueryState state="error" onRetry={() => void sessionQuery.refetch()} />;
  }

  const modelNames = (promptsQuery.data ?? []).map((prompt) => prompt.modelName);
  const folders = foldersQuery.data ?? [];
  const providerConfigs = providersQuery.data ?? [];
  const keys = keysQuery.data ?? [];

  function closeCreate() {
    setCreating(false);
    setName('');
    setScope([]);
    setNamespaces([]);
  }

  function editScope(key: ScopeTarget) {
    setEditing({
      key,
      draft: {
        scopeModelNames: key.scopeModelNames,
        scopeNamespaces: key.scopeNamespaces,
        observeProviderConfigId: key.observeProviderConfigId,
        observeNamespace: key.observeNamespace,
      },
    });
  }

  function patchDraft(patch: Partial<KeyScope>) {
    setEditing((current) => (current ? { ...current, draft: { ...current.draft, ...patch } } : current));
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
                {secret.secret}
              </code>
              <Button
                type="button"
                intent="neutral"
                size="small"
                leadingIcon={
                  copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />
                }
                onClick={() => void copySecret(secret.secret)}
              >
                {t(copied ? 'keys.created.copied' : 'keys.created.copy')}
              </Button>
            </div>
          </div>
          {/* The gap that cost three failed attempts to find. A key minted
              with folders looks finished — it has a scope, it authenticates,
              and every call from an unadopted product is refused with a 404
              that by design says nothing about why (A-116). The only moment
              anybody is looking at this key with the intent to wire something
              up is right now, so the second switch is named right now.

              Only when folders were granted: a key scoped to individual model
              names is an ordinary integrated key and has no reason to observe,
              and a prompt shown to everyone is a prompt nobody reads. */}
          {secret.scopeNamespaces.length > 0 ? (
            <Notification tone="info" title={t('keys.created.observeTitle')}>
              <div className="grid gap-3 justify-items-start">
                <p>
                  {t('keys.created.observeBody', {
                    folders: secret.scopeNamespaces.map((namespace) => `${namespace}/*`).join(', '),
                  })}
                </p>
                <Button
                  type="button"
                  intent="neutral"
                  size="small"
                  leadingIcon={<Eye aria-hidden weight="fill" className="size-4" />}
                  onClick={() =>
                    editScope({
                      keyId: secret.keyId,
                      name: secret.name,
                      scopeModelNames: secret.scopeModelNames,
                      scopeNamespaces: secret.scopeNamespaces,
                      // Both null by construction: `KeyCreate` carries no
                      // `observe_*` fields, so a key cannot be minted observing
                      // (A-152). Reading them off the response would be reading
                      // fields that are not on it.
                      observeProviderConfigId: null,
                      observeNamespace: null,
                    })
                  }
                >
                  {t('keys.created.observeAction')}
                </Button>
              </div>
            </Notification>
          ) : null}

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
                      {reachLabel(t, key)}
                      {' · '}
                      {t('keys.list.created', { date: format.date(key.createdAt) })}
                      {' · '}
                      {key.lastUsedAt
                        ? t('keys.list.lastUsed', { date: format.date(key.lastUsedAt) })
                        : t('keys.list.neverUsed')}
                    </p>
                    {key.scopeNamespaces.length > 0 ? (
                      <p className="flex items-center gap-1.5 truncate font-mono text-caption text-muted">
                        <FolderSimple aria-hidden weight="fill" className="size-3.5 shrink-0 text-primary" />
                        {key.scopeNamespaces.map((namespace) => `${namespace}/*`).join(', ')}
                      </p>
                    ) : null}
                    {key.scopeModelNames.length > 0 ? (
                      <p className="truncate font-mono text-caption text-muted">
                        {key.scopeModelNames.join(', ')}
                      </p>
                    ) : null}
                    {/* ADR-0059. Shown on the row rather than behind the dialog
                        because "this key forwards what I cannot resolve" is the
                        one property of a key somebody would want to spot without
                        opening anything. */}
                    {keyObserves(key) ? (
                      <p className="flex items-center gap-1.5 text-caption text-primary">
                        <Eye aria-hidden weight="fill" className="size-3.5 shrink-0" />
                        {t('keys.list.observing', { namespace: key.observeNamespace })}
                      </p>
                    ) : key.scopeNamespaces.length > 0 ? (
                      /* Stated, not warned about. A folder-scoped key that does
                         not observe is a perfectly ordinary integrated key, and
                         styling this as a problem would nag every one of them.
                         It is here because a key minted before the callout above
                         existed has no other place to learn it, and because the
                         failure it explains is a 404 that explains nothing. */
                      <p className="flex items-center gap-1.5 text-caption text-muted">
                        <EyeSlash aria-hidden className="size-3.5 shrink-0" />
                        {t('keys.list.notObserving')}
                      </p>
                    ) : null}
                  </div>
                </div>
                {key.revokedAt ? (
                  <span className="rounded-tag bg-disabled px-2 py-0.5 text-caption text-disabled-text">
                    {t('keys.list.revoked', { date: format.date(key.revokedAt) })}
                  </span>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      intent="neutral"
                      size="small"
                      leadingIcon={<SlidersHorizontal aria-hidden className="size-4" />}
                      onClick={() => editScope(key)}
                    >
                      {t('keys.list.editScope')}
                    </Button>
                    <Button
                      type="button"
                      intent="danger"
                      size="small"
                      leadingIcon={<Trash aria-hidden className="size-4" />}
                      onClick={() => setPendingRevoke(key)}
                    >
                      {t('keys.list.revoke')}
                    </Button>
                  </div>
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
            { name: name.trim(), scopeModelNames: scope, scopeNamespaces: namespaces },
            {
              onSuccess: (created) => {
                setSecret(created);
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
          {/* Folders first, and above the prompt list on purpose: it is the
              answer for almost every product, and a screen that offers the
              thousand-checkbox version first teaches people to use it. */}
          <TickList
            legend={t('keys.create.namespaceLabel')}
            hint={t('keys.create.namespaceHint')}
            empty={t('keys.create.noFolders')}
            items={folders.map((folder) => ({
              value: folder.id,
              label: `${folder.id}/*`,
              meta: t('keys.scope.folderPrompts', { count: folder.promptCount }),
            }))}
            selected={namespaces}
            onToggle={(value, on) =>
              setNamespaces((current) =>
                on ? [...current, value] : current.filter((item) => item !== value),
              )
            }
          />
          <TickList
            legend={t('keys.create.scopeLabel')}
            hint={t('keys.create.scopeHint')}
            empty={t('keys.create.noPrompts')}
            items={modelNames.map((modelName) => ({ value: modelName, label: modelName }))}
            selected={scope}
            onToggle={(value, on) =>
              setScope((current) =>
                on ? [...current, value] : current.filter((item) => item !== value),
              )
            }
          />
          {namespaces.length === 0 && scope.length === 0 ? (
            <Notification tone="info" title={t('keys.create.emptyScopeTitle')}>
              {t('keys.create.emptyScopeBody')}
            </Notification>
          ) : null}
          {/* Not a Notification: this is a caption on the two pickers above, and
              dressing it as an alert would put it in competition with the empty
              scope warning it sits beside. */}
          {namespaces.length > 0 ? (
            <p className="text-caption text-muted">{t('keys.create.observeNote')}</p>
          ) : null}
        </div>
      </Modal>

      {/* One dialog for the whole reach, because `PUT .../scope` replaces the
          whole reach. Splitting it into "edit folders" and "edit observation"
          would be two calls where the second silently undoes the first — the
          route takes the array you want to end up with, never a delta. */}
      <Modal
        open={editing !== undefined}
        title={t('keys.scope.title', { name: editing?.key.name ?? '' })}
        description={t('keys.scope.description')}
        confirmLabel={t('keys.scope.confirm')}
        confirmLoading={setScopeOf.isPending}
        onClose={() => setEditing(undefined)}
        onConfirm={() => {
          const target = editing;
          if (!target) return;
          setScopeOf.mutate(
            { keyId: target.key.keyId, scope: target.draft },
            { onSuccess: () => setEditing(undefined) },
          );
        }}
      >
        <div className="grid gap-4">
          {setScopeOf.isError ? (
            <Notification tone="error" title={t('keys.scope.error')}>
              {t('keys.scope.errorHint')}
            </Notification>
          ) : null}

          <TickList
            legend={t('keys.create.namespaceLabel')}
            hint={t('keys.create.namespaceHint')}
            empty={t('keys.create.noFolders')}
            items={folders.map((folder) => ({
              value: folder.id,
              label: `${folder.id}/*`,
              meta: t('keys.scope.folderPrompts', { count: folder.promptCount }),
            }))}
            selected={editing?.draft.scopeNamespaces ?? []}
            onToggle={(value, on) =>
              patchDraft({
                scopeNamespaces: on
                  ? [...(editing?.draft.scopeNamespaces ?? []), value]
                  : (editing?.draft.scopeNamespaces ?? []).filter((item) => item !== value),
              })
            }
          />
          <TickList
            legend={t('keys.create.scopeLabel')}
            hint={t('keys.create.scopeHint')}
            empty={t('keys.create.noPrompts')}
            items={modelNames.map((modelName) => ({ value: modelName, label: modelName }))}
            selected={editing?.draft.scopeModelNames ?? []}
            onToggle={(value, on) =>
              patchDraft({
                scopeModelNames: on
                  ? [...(editing?.draft.scopeModelNames ?? []), value]
                  : (editing?.draft.scopeModelNames ?? []).filter((item) => item !== value),
              })
            }
          />

          <fieldset className="grid gap-2 rounded-modal border border-border p-3">
            <legend className="flex items-center gap-1.5 px-1 text-body font-medium text-ink">
              <Eye aria-hidden weight="fill" className="size-4 text-primary" />
              {t('keys.scope.observeLabel')}
            </legend>
            <p className="text-caption text-muted">{t('keys.scope.observeHint')}</p>

            <label className="flex cursor-pointer items-center gap-2 py-1 text-body font-normal text-ink">
              <input
                type="checkbox"
                checked={
                  editing !== undefined &&
                  (editing.draft.observeProviderConfigId !== null ||
                    editing.draft.observeNamespace !== null)
                }
                onChange={(event) =>
                  // All or nothing, and cleared as a pair. The command answers a
                  // half-set pair with a 422 and the check constraint refuses it
                  // again underneath, so offering two independent controls would
                  // only be a way to reach a state the server rejects.
                  patchDraft(
                    event.target.checked
                      ? {
                          observeProviderConfigId: UNSET,
                          observeNamespace: editing?.key.observeNamespace ?? '',
                        }
                      : { observeProviderConfigId: null, observeNamespace: null },
                  )
                }
                className="size-4 accent-primary"
              />
              {t('keys.scope.observeEnable')}
            </label>

            {editing !== undefined &&
            (editing.draft.observeProviderConfigId !== null ||
              editing.draft.observeNamespace !== null) ? (
              <div className="grid gap-3 border-t border-border pt-3">
                <Select
                  label={t('keys.scope.observeProviderLabel')}
                  value={editing.draft.observeProviderConfigId ?? UNSET}
                  options={[
                    { value: UNSET, label: t('keys.scope.observeProviderUnset') },
                    ...providerConfigs.map((config) => ({
                      value: config.provider_config_id,
                      label:
                        config.verification_status === 'passed'
                          ? config.display_name
                          : t('keys.scope.observeProviderUnverified', { name: config.display_name }),
                    })),
                  ]}
                  onValueChange={(value) => patchDraft({ observeProviderConfigId: value })}
                />
                <Input
                  label={t('keys.scope.observeNamespaceLabel')}
                  hint={t('keys.scope.observeNamespaceHint')}
                  value={editing.draft.observeNamespace ?? ''}
                  onChange={(event) => patchDraft({ observeNamespace: event.target.value })}
                />
                <Notification tone="info" title={t('keys.scope.observePrivateTitle')}>
                  {t('keys.scope.observePrivateBody')}
                </Notification>
              </div>
            ) : (
              /* An unticked checkbox states that a thing is off; it does not
                 state what off COSTS. The cost here is a refusal that is
                 byte-identical to an unknown prompt's (A-116) — the one error
                 somebody hits while wiring this up is the one error that cannot
                 point at this box. */
              <p className="border-t border-border pt-3 text-caption text-muted">
                <span className="font-medium text-ink">{t('keys.scope.observeOffTitle')}</span>{' '}
                {t('keys.scope.observeOffBody')}
              </p>
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


/**
 * What the scope dialog needs to open, which is less than a whole key.
 *
 * A `Pick` rather than `ApiKey` because the dialog is also opened on a key that
 * has just been minted and is not in the list yet — `CreatedApiKey` has no
 * `createdBy`, `revokedAt` or `lastUsedAt`, and inventing them to satisfy a
 * type would be inventing facts about a row nobody has read back.
 */
type ScopeTarget = Pick<
  ApiKey,
  | 'keyId'
  | 'name'
  | 'scopeModelNames'
  | 'scopeNamespaces'
  | 'observeProviderConfigId'
  | 'observeNamespace'
>;

/**
 * A reach summary in one line: folders, then prompts, then the empty case.
 *
 * Folders lead because that is the grant somebody actually made — "reaches 3
 * folders" stays true as prompts are added to them, where a prompt count would
 * read as stale the moment the folder grows.
 */
function reachLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  key: ApiKey,
): string {
  const parts: string[] = [];
  if (key.scopeNamespaces.length > 0) {
    parts.push(t('keys.list.namespaceCount', { count: key.scopeNamespaces.length }));
  }
  if (key.scopeModelNames.length > 0) {
    parts.push(t('keys.list.scopeCount', { count: key.scopeModelNames.length }));
  }
  return parts.length === 0 ? t('keys.list.scopeEmpty') : parts.join(t('keys.list.reachJoin'));
}

interface TickItem {
  value: string;
  label: string;
  meta?: string;
}

/**
 * A scrolling list of ticks. Shared by the create dialog and the scope dialog so
 * the two cannot drift into disagreeing about what a folder row looks like —
 * they are the same grant, made at two moments.
 */
function TickList({
  legend,
  hint,
  empty,
  items,
  selected,
  onToggle,
}: {
  legend: string;
  hint: string;
  empty: string;
  items: TickItem[];
  selected: string[];
  onToggle: (value: string, on: boolean) => void;
}) {
  return (
    <fieldset className="grid gap-2">
      <legend className="text-body font-medium text-ink">{legend}</legend>
      <p className="text-caption text-muted">{hint}</p>
      {items.length === 0 ? (
        <p className="text-caption text-muted">{empty}</p>
      ) : (
        <div className="grid max-h-56 gap-1 overflow-y-auto rounded-lg border border-border p-2">
          {items.map((item) => (
            <label
              key={item.value}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-body font-normal text-ink hover:bg-subtle"
            >
              <input
                type="checkbox"
                checked={selected.includes(item.value)}
                onChange={(event) => onToggle(item.value, event.target.checked)}
                className="size-4 shrink-0 accent-primary"
              />
              <span className="min-w-0 flex-1 truncate font-mono text-caption">{item.label}</span>
              {item.meta ? <span className="shrink-0 text-caption text-muted">{item.meta}</span> : null}
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}
