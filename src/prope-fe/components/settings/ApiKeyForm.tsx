import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Eye, EyeSlash } from '@phosphor-icons/react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { ApiKey } from './ApiKeysPanel';
import { cn } from '@/lib/cn';

interface ApiKeyFormProps {
  providerId: string;
  providerName: string;
  existingKey?: ApiKey | null;
  onSave: (key: Omit<ApiKey, 'id'>) => void;
  onCancel: () => void;
}

const PRESET_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet-20240620', 'claude-3-5-haiku-20240307', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
  google: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro'],
  custom: [],
};

export function ApiKeyForm({ providerId, providerName, existingKey, onSave, onCancel }: ApiKeyFormProps) {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState(existingKey?.apiKey ?? '');
  const [name, setName] = useState(existingKey?.name ?? `${providerName} Key`);
  const [model, setModel] = useState(existingKey?.defaultModel ?? '');
  const [baseUrl, setBaseUrl] = useState(existingKey?.baseUrl ?? '');
  const [showApiKey, setShowApiKey] = useState(false);
  const [showBaseUrl, setShowBaseUrl] = useState(false);
  const [errors, setErrors] = useState<{ apiKey?: string; name?: string; model?: string }>({});

  const isCustomProvider = providerId === 'custom';
  const presetModels = PRESET_MODELS[providerId] ?? [];

  const validate = (): boolean => {
    const newErrors: typeof errors = {};

    if (!name.trim()) {
      newErrors.name = t('settings.apiKeys.validation.nameRequired');
    }

    if (!apiKey.trim()) {
      newErrors.apiKey = t('settings.apiKeys.validation.apiKeyRequired');
    }

    if (!model.trim() && isCustomProvider) {
      newErrors.model = t('settings.apiKeys.validation.modelRequired');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    onSave({
      providerId,
      name: name.trim(),
      apiKey: apiKey.trim(),
      defaultModel: model.trim() || undefined,
      baseUrl: isCustomProvider && baseUrl.trim() ? baseUrl.trim() : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <p className="text-caption text-muted">{t('settings.apiKeys.provider')}</p>
        <p className="text-body font-medium text-ink">{providerName}</p>
      </div>

      <Input
        label={t('settings.apiKeys.keyName')}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t('settings.apiKeys.keyNamePlaceholder')}
        error={errors.name}
      />

      {isCustomProvider ? (
        <>
          <div className="space-y-2">
            <label className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink">
              <span>{t('settings.apiKeys.baseUrl')}</span>
            </label>
            <div className="relative">
              <input
                type={showBaseUrl ? 'text' : 'password'}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={t('settings.apiKeys.baseUrlPlaceholder')}
                className={cn(
                  'h-11 w-full min-w-0 cursor-text rounded-lg border border-border bg-surface px-3 pr-10 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25',
                  errors.model && 'border-danger-strong focus:border-danger-strong focus:ring-danger-strong/25'
                )}
              />
              <button
                type="button"
                onClick={() => setShowBaseUrl(!showBaseUrl)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
                aria-label={showBaseUrl ? t('settings.apiKeys.hideBaseUrl') : t('settings.apiKeys.showBaseUrl')}
              >
                {showBaseUrl ? <EyeSlash aria-hidden className="size-5" /> : <Eye aria-hidden className="size-5" />}
              </button>
            </div>
          </div>

          <Input
            label={t('settings.apiKeys.model')}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t('settings.apiKeys.modelPlaceholder')}
            error={errors.model}
            hint={t('settings.apiKeys.modelHint')}
          />
        </>
      ) : presetModels.length > 0 ? (
        <div className="space-y-2">
          <label className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink">
            <span>{t('settings.apiKeys.model')}</span>
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-11 w-full min-w-0 cursor-pointer rounded-lg border border-border bg-surface px-3 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) focus:border-focus focus:ring-2 focus:ring-focus/25"
          >
            <option value="">{t('settings.apiKeys.selectModel')}</option>
            {presetModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          {!model && (
            <span className="text-caption text-muted">{t('settings.apiKeys.selectModelHint')}</span>
          )}
        </div>
      ) : (
        <Input
          label={t('settings.apiKeys.model')}
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={t('settings.apiKeys.modelPlaceholder')}
        />
      )}

      <div className="space-y-2">
        <label className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink">
          <span>{t('settings.apiKeys.apiKey')}</span>
        </label>
        <div className="relative">
          <input
            type={showApiKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t('settings.apiKeys.apiKeyPlaceholder')}
            className={cn(
              'h-11 w-full min-w-0 cursor-text rounded-lg border border-border bg-surface px-3 pr-10 text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25',
              errors.apiKey && 'border-danger-strong focus:border-danger-strong focus:ring-danger-strong/25'
            )}
          />
          <button
            type="button"
            onClick={() => setShowApiKey(!showApiKey)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
            aria-label={showApiKey ? t('settings.apiKeys.hideApiKey') : t('settings.apiKeys.showApiKey')}
          >
            {showApiKey ? <EyeSlash aria-hidden className="size-5" /> : <Eye aria-hidden className="size-5" />}
          </button>
        </div>
        {errors.apiKey && <span className="text-caption font-normal text-danger-text">{errors.apiKey}</span>}
        <span className="text-caption text-muted">{t('settings.apiKeys.apiKeySecurityNote')}</span>
      </div>

      <div className="flex gap-2 pt-2">
        <Button type="button" intent="neutral" onClick={onCancel} className="flex-1">
          {t('common.cancel')}
        </Button>
        <Button type="submit" intent="primary" className="flex-1">
          {existingKey ? t('settings.apiKeys.updateKey') : t('settings.apiKeys.saveKey')}
        </Button>
      </div>
    </form>
  );
}
