import { Check, Copy, Key } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Notification } from '@/components/Notification';
import { SegmentedControl } from '@/components/SegmentedControl';
import { Button } from '@/components/ui/Button';
import {
  SNIPPET_LANGUAGES,
  buildSnippet,
  gatewayBaseUrl,
  type SnippetLanguage,
} from '@/features/prompt-lifecycle/snippets';

interface ApiKeyDemoCardProps {
  /** `namespace/name` — what the consumer passes as `model`. */
  modelName: string;
  released: boolean;
}

const PLACEHOLDER_KEY = 'prope_key_...';

/**
 * "Tài liệu + API key demo" for the Content tab.
 *
 * The snippet names the prompt and never the revision, and carries a masked
 * placeholder rather than a credential — the plaintext appeared once, in the key
 * creation response, and is unrecoverable by design. The create-key action goes
 * to the existing keys screen instead of minting here, because a key's scopes
 * are a workspace decision, not a prompt-detail side effect.
 */
export function ApiKeyDemoCard({ modelName, released }: ApiKeyDemoCardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [language, setLanguage] = useState<SnippetLanguage>('curl');
  const [copied, setCopied] = useState(false);

  const snippet = buildSnippet(language, {
    modelName,
    baseUrl: gatewayBaseUrl(),
    apiKey: PLACEHOLDER_KEY,
    variables: [],
  });

  const copy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <section aria-labelledby="api-key-heading" className="rounded-modal border border-border bg-surface shadow-panel">
      <div className="border-b border-border p-4 sm:p-5">
        <h2 id="api-key-heading" className="font-display text-heading-3 text-ink">{t('lifecycle.surface.apiKey.title')}</h2>
        <p className="mt-1 text-body text-muted">{t('lifecycle.surface.apiKey.description', { model: modelName })}</p>
      </div>
      <div className="grid gap-3 p-4 sm:p-5">
        {!released ? <Notification tone="info" title={t('keys.code.notReleased')}>{t('keys.code.notReleasedHint')}</Notification> : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SegmentedControl
            className="max-w-none"
            label={t('keys.code.languageLabel')}
            name="content-snippet-language"
            options={SNIPPET_LANGUAGES.map((candidate) => ({ value: candidate, label: t(`keys.code.language.${candidate}`) }))}
            value={language}
            onValueChange={(value) => setLanguage(value as SnippetLanguage)}
          />
          <Button
            type="button"
            intent="ghost"
            size="small"
            leadingIcon={copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />}
            onClick={() => void copy()}
          >
            {t(copied ? 'keys.code.copied' : 'keys.code.copyCode')}
          </Button>
        </div>
        <pre className="max-h-96 overflow-auto rounded-modal bg-ink p-4 font-mono text-caption text-inverse">{snippet}</pre>
        <div className="flex justify-end">
          <Button type="button" leadingIcon={<Key aria-hidden className="size-4" />} onClick={() => void navigate('/app/settings/keys')}>
            {t('lifecycle.surface.apiKey.createKey')}
          </Button>
        </div>
      </div>
    </section>
  );
}
