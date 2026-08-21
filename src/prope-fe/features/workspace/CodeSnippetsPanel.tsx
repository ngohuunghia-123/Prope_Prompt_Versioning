import { Check, Copy, ShieldCheck } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Notification } from '@/components/Notification';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { promptsOptions } from '@/features/prompt-lifecycle/queries';
import {
  SNIPPET_LANGUAGES,
  buildSnippet,
  gatewayBaseUrl,
  type SnippetLanguage,
} from '@/features/prompt-lifecycle/snippets';
import { useSetKeyScopeMutation, workspaceKeysOptions } from '@/features/workspace/keyQueries';
import { keysAreLive } from '@/features/workspace/keysApi';
import { isKeyLive, maskedKey } from '@/features/workspace/keyTypes';

interface CodeSnippetsPanelProps {
  workspaceId: string;
}

const PLACEHOLDER_KEY = 'prope_key_...';

/**
 * Which prompt, on which key, in three languages.
 *
 * **It sits under the key list because it is the key list's consequence.** A
 * snippet is a credential plus a model name, and the two decisions — mint a key
 * for this app, let that key reach this prompt — are the same decision seen from
 * the consuming side. Splitting them across two screens is what made somebody
 * copy a snippet, run it, and meet a not-found they had no way to read.
 *
 * **Scope is granted explicitly here and never silently.** A key resolves a model
 * name by exact membership with no wildcard, so a prompt outside the scope
 * answers the same not-found an unknown model gets — deliberately, so a leaked
 * key cannot enumerate the registry. Widening it is therefore a real permission
 * change, and it gets a button rather than an effect.
 *
 * **The masked value is all a snippet can show.** The stored row keeps a SHA-256
 * digest and four characters; the plaintext appeared once, in the creation
 * response above, and is unrecoverable. A snippet carrying a mask is a snippet
 * somebody must paste their own key into, which is the correct amount of friction
 * for a credential.
 */
export function CodeSnippetsPanel({ workspaceId }: CodeSnippetsPanelProps) {
  const { t } = useTranslation();
  const live = keysAreLive();
  const keysQuery = useQuery({
    ...workspaceKeysOptions(workspaceId),
    enabled: live && workspaceId !== '',
  });
  const promptsQuery = useQuery(promptsOptions);
  const setScope = useSetKeyScopeMutation(workspaceId);

  const [language, setLanguage] = useState<SnippetLanguage>('python');
  const [copied, setCopied] = useState<string>();
  const [chosenPromptId, setChosenPromptId] = useState<string>();
  const [chosenKeyId, setChosenKeyId] = useState<string>();

  const prompts = promptsQuery.data ?? [];
  const prompt = prompts.find((item) => item.id === chosenPromptId) ?? prompts[0];
  const liveKeys = (keysQuery.data ?? []).filter(isKeyLive);
  const selected = liveKeys.find((key) => key.keyId === chosenKeyId) ?? liveKeys[0];

  const modelName = prompt?.modelName ?? '';
  // INT-004 resolves a name that is listed OR whose folder is scoped, so the
  // question this screen asks — "can this key call this prompt?" — has to ask
  // both. Checking only the list would offer to grant a prompt the key already
  // reaches through its folder, and the grant would then write a redundant entry
  // that never goes away.
  const inScope =
    selected !== undefined &&
    (selected.scopeModelNames.includes(modelName) ||
      selected.scopeNamespaces.includes(modelName.split('/')[0] ?? ''));
  const released = prompt?.status === 'inUse';

  async function copy(value: string, token: string) {
    await navigator.clipboard.writeText(value);
    setCopied(token);
    window.setTimeout(() => setCopied((current) => (current === token ? undefined : current)), 1600);
  }

  const snippet = buildSnippet(language, {
    modelName,
    baseUrl: gatewayBaseUrl(),
    apiKey: selected ? maskedKey(selected) : PLACEHOLDER_KEY,
    // The released body's `{{variables}}` are not on the list endpoint, so the
    // snippet shows the call shape rather than a filled-in variable set. The
    // playground is where a body's variables are discovered.
    variables: [],
  });

  if (prompts.length === 0) {
    return (
      <Card title={t('keys.code.title')} description={t('keys.code.description')}>
        <p className="rounded-modal border border-dashed border-border p-8 text-center text-muted">
          {t('keys.code.noPrompt')}
        </p>
      </Card>
    );
  }

  return (
    <Card title={t('keys.code.title')} description={t('keys.code.description')}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Select
          label={t('keys.code.promptLabel')}
          options={prompts.map((item) => ({ value: item.id, label: item.title }))}
          value={prompt?.id ?? ''}
          onValueChange={setChosenPromptId}
        />
        {liveKeys.length > 0 && selected ? (
          <Select
            label={t('keys.code.keySelect')}
            options={liveKeys.map((key) => ({ value: key.keyId, label: key.name }))}
            value={selected.keyId}
            onValueChange={setChosenKeyId}
          />
        ) : null}
      </div>

      {!selected ? (
        <Notification tone="info" title={t('keys.code.noKey')}>
          {t('keys.code.noKeyHint')}
        </Notification>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-modal border border-border bg-subtle p-4">
          <div className="min-w-0">
            <p className="truncate font-mono text-caption text-ink">{maskedKey(selected)}</p>
            <p className="text-caption text-muted">
              {setScope.isPending
                ? t('keys.code.granting')
                : inScope
                  ? t('keys.code.scopeIncludes', { model: modelName })
                  : t('keys.code.scopeMissing', { model: modelName })}
            </p>
          </div>
          {inScope || setScope.isPending ? (
            <p className="text-caption text-muted">{t('keys.code.secretGone')}</p>
          ) : (
            <Button
              type="button"
              intent="neutral"
              size="small"
              leadingIcon={<ShieldCheck aria-hidden className="size-4" />}
              onClick={() =>
                // The whole reach, every time. `PUT .../scope` replaces what it
                // is given, so this has to carry the folders and the observe
                // pair forward — sending only the model names would quietly
                // revoke both, and turning observation off is precisely the
                // silent failure ADR-0059's capability cannot afford.
                setScope.mutate({
                  keyId: selected.keyId,
                  scope: {
                    scopeModelNames: [...selected.scopeModelNames, modelName],
                    scopeNamespaces: selected.scopeNamespaces,
                    observeProviderConfigId: selected.observeProviderConfigId,
                    observeNamespace: selected.observeNamespace,
                  },
                })
              }
            >
              {t('keys.code.grantScope')}
            </Button>
          )}
        </div>
      )}

      {setScope.isError ? (
        <Notification tone="error" title={t('keys.code.grantError')}>
          {t('keys.code.grantErrorHint')}
        </Notification>
      ) : null}

      {!released ? (
        <Notification tone="info" title={t('keys.code.notReleased')}>
          {t('keys.code.notReleasedHint')}
        </Notification>
      ) : null}

      <SegmentedControl
        className="max-w-none"
        label={t('keys.code.languageLabel')}
        name="code-snippet-language"
        options={SNIPPET_LANGUAGES.map((candidate) => ({
          value: candidate,
          label: t(`keys.code.language.${candidate}`),
        }))}
        value={language}
        onValueChange={(value) => setLanguage(value as SnippetLanguage)}
      />
      <div className="grid gap-2">
        <div className="flex items-center justify-between gap-2">
          <code className="truncate text-caption text-muted">{modelName}</code>
          <Button
            type="button"
            intent="ghost"
            size="small"
            leadingIcon={
              copied === language ? (
                <Check aria-hidden className="size-4" />
              ) : (
                <Copy aria-hidden className="size-4" />
              )
            }
            onClick={() => void copy(snippet, language)}
          >
            {t(copied === language ? 'keys.code.copied' : 'keys.code.copyCode')}
          </Button>
        </div>
        <pre className="max-h-96 overflow-auto rounded-modal bg-ink p-4 font-mono text-caption text-inverse">
          {snippet}
        </pre>
      </div>
    </Card>
  );
}
