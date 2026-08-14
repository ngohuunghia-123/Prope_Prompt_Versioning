import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Pencil, Trash, Check, Warning, Key, CaretRight } from '@phosphor-icons/react';
import { Button } from '@/components/ui/Button';
import { ApiKeyForm } from './ApiKeyForm';

export interface Provider {
  id: string;
  name: string;
  logo?: string;
  defaultModel?: string;
  isConfigured: boolean;
}

const MOCK_PROVIDERS: Provider[] = [
  { id: 'openai', name: 'OpenAI', defaultModel: 'gpt-4o', isConfigured: true },
  { id: 'anthropic', name: 'Anthropic', defaultModel: 'claude-3-5-sonnet-20240620', isConfigured: true },
  { id: 'google', name: 'Google', defaultModel: 'gemini-1.5-pro', isConfigured: false },
];

export interface ApiKey {
  id: string;
  providerId: string;
  name: string;
  apiKey: string;
  baseUrl?: string;
  defaultModel?: string;
}

const MOCK_API_KEYS: ApiKey[] = [
  { id: '1', providerId: 'openai', name: 'Production Key', apiKey: 'sk-****', defaultModel: 'gpt-4o' },
  { id: '2', providerId: 'anthropic', name: 'Claude API', apiKey: 'sk-ant-****', defaultModel: 'claude-3-5-sonnet-20240620' },
];

export function ApiKeysPanel() {
  const { t } = useTranslation();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(MOCK_API_KEYS);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [showProviders, setShowProviders] = useState(false);

  const handleAddKey = () => {
    setShowProviders(true);
    setShowForm(false);
    setEditingKey(null);
  };

  const handleSelectProvider = (providerId: string) => {
    setSelectedProvider(providerId);
    setShowForm(true);
    setShowProviders(false);
  };

  const handleEditKey = (key: ApiKey) => {
    setEditingKey(key);
    setSelectedProvider(key.providerId);
    setShowForm(true);
    setShowProviders(false);
  };

  const handleDeleteKey = (keyId: string) => {
    setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
  };

  const handleSaveKey = (keyData: Omit<ApiKey, 'id'>) => {
    if (editingKey) {
      setApiKeys((prev) =>
        prev.map((k) => (k.id === editingKey.id ? { ...keyData, id: editingKey.id } : k))
      );
    } else {
      setApiKeys((prev) => [...prev, { ...keyData, id: Date.now().toString() }]);
    }
    setShowForm(false);
    setSelectedProvider(null);
    setEditingKey(null);
  };

  const handleCancel = () => {
    setShowForm(false);
    setSelectedProvider(null);
    setEditingKey(null);
    setShowProviders(false);
  };

  const getProviderName = (providerId: string) => {
    const provider = MOCK_PROVIDERS.find((p) => p.id === providerId);
    return provider?.name ?? providerId;
  };

  if (showForm && selectedProvider) {
    return (
      <ApiKeyForm
        providerId={selectedProvider}
        providerName={getProviderName(selectedProvider)}
        existingKey={editingKey}
        onSave={handleSaveKey}
        onCancel={handleCancel}
      />
    );
  }

  if (showProviders) {
    return (
      <div className="space-y-4">
        <div className="space-y-2">
          <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
            {t('settings.apiKeys.popularProviders')}
          </h3>
          <div className="space-y-1">
            {MOCK_PROVIDERS.filter((p) => p.isConfigured).map((provider) => (
              <button
                key={provider.id}
                type="button"
                onClick={() => handleSelectProvider(provider.id)}
                className="flex w-full min-w-0 items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:border-primary hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-focus"
              >
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted/30 text-muted">
                    <Key aria-hidden className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-body font-medium text-ink">{provider.name}</p>
                    {provider.defaultModel && (
                      <p className="text-caption text-muted">{provider.defaultModel}</p>
                    )}
                  </div>
                </div>
                <CaretRight aria-hidden className="size-4 shrink-0 text-muted" />
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
            {t('settings.apiKeys.customProvider')}
          </h3>
          <button
            type="button"
            onClick={() => handleSelectProvider('custom')}
            className="flex w-full min-w-0 items-center justify-between rounded-lg border border-dashed border-border bg-surface px-3 py-2.5 text-left transition-colors hover:border-primary hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-focus"
          >
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted/30 text-muted">
                <Plus aria-hidden className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-body font-medium text-ink">{t('settings.apiKeys.addCustomProvider')}</p>
                <p className="text-caption text-muted">{t('settings.apiKeys.customProviderHint')}</p>
              </div>
            </div>
            <CaretRight aria-hidden className="size-4 shrink-0 text-muted" />
          </button>
        </div>

        <Button type="button" intent="neutral" onClick={handleCancel} className="w-full">
          {t('common.cancel')}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-caption font-medium text-muted uppercase tracking-wider">
            {t('settings.apiKeys.configuredKeys')}
          </h3>
          <Button
            type="button"
            size="default"
            intent="primary"
            leadingIcon={<Plus aria-hidden />}
            onClick={handleAddKey}
            className="w-full"
          >
            {t('settings.apiKeys.addKey')}
          </Button>
        </div>

        {apiKeys.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-surface p-6 text-center">
            <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-full bg-muted/30">
              <Key aria-hidden className="size-6 text-muted" />
            </div>
            <p className="text-body text-muted">{t('settings.apiKeys.noKeysConfigured')}</p>
            <p className="mt-1 text-caption text-muted">{t('settings.apiKeys.noKeysHint')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {apiKeys.map((key) => (
              <div
                key={key.id}
                className="flex min-w-0 items-center justify-between rounded-lg border border-border bg-surface px-3 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-body font-medium text-ink">{key.name}</p>
                    <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-caption text-success">
                      <Check aria-hidden className="size-3" weight="bold" />
                      {t('settings.apiKeys.configured')}
                    </span>
                  </div>
                  <p className="text-caption text-muted">
                    {getProviderName(key.providerId)} · {key.apiKey}
                    {key.defaultModel && ` · ${key.defaultModel}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    type="button"
                    size="icon"
                    intent="neutral"
                    onClick={() => handleEditKey(key)}
                    aria-label={t('common.edit')}
                    className="size-8"
                  >
                    <Pencil aria-hidden className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    intent="neutral"
                    onClick={() => handleDeleteKey(key.id)}
                    aria-label={t('common.delete')}
                    className="size-8 text-danger hover:bg-danger/10 hover:text-danger"
                  >
                    <Trash aria-hidden className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-border bg-navigation-surface/50 p-3">
        <div className="flex items-start gap-2">
          <Warning aria-hidden className="mt-0.5 size-4 shrink-0 text-muted" />
          <p className="text-caption text-muted">{t('settings.apiKeys.securityNote')}</p>
        </div>
      </div>
    </div>
  );
}
