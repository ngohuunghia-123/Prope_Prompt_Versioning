import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { providerConfigsOptions } from '@/features/prompt-lifecycle/queries';

/**
 * Turn a `provider_config_id` into the name somebody gave it.
 *
 * `PromptDetail.provider` carries the id of the configuration the latest
 * revision bound to, because that is what the revision stores — the registry has
 * no reason to know a vendor's display name. Rendering the id raw is how a
 * detail panel ends up reading `Provider: prv_01J8…`, so the lookup happens
 * here, once, against the list every provider surface already has cached.
 *
 * A configuration that has since been deleted keeps its id in the revision and
 * resolves to nothing, which is the honest answer: the binding is a value, not a
 * foreign key, and the thing it named is gone.
 */
export function useProviderName(providerConfigId: string): string | undefined {
  const { t } = useTranslation();
  const { data } = useQuery(providerConfigsOptions);
  if (!providerConfigId) return undefined;
  const match = data?.find((provider) => provider.provider_config_id === providerConfigId);
  return match ? match.display_name : t('lifecycle.providers.deletedConfig');
}
