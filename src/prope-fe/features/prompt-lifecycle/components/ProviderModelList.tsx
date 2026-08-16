import { ArrowsClockwise, CurrencyDollar, Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tag } from '@/components/Tag';
import { PRICE_UNIT_SCALE, type PriceRow } from '@/features/prompt-lifecycle/providerTypes';
import {
  priceRowsOptions,
  providerModelsOptions,
  useAddProviderModelMutation,
  useRefreshProviderModelsMutation,
} from '@/features/prompt-lifecycle/queries';
import { ModelPriceDialog, type ModelPriceTarget } from '@/features/prompt-lifecycle/components/ModelPriceDialog';

/**
 * The row currently in force for a model.
 *
 * `GET /prices` returns superseded rows too, on purpose — a cost recorded under
 * an old price has to stay explicable. Exactly one row per key has a null
 * `effective_to`, and that is the one this screen is about.
 */
function priceInForce(rows: PriceRow[], providerId: string, modelId: string): PriceRow | undefined {
  return rows.find((row) =>
    row.provider_config_id === providerId
    && row.upstream_model === modelId
    && (row.effective_to === null || row.effective_to === undefined));
}

/**
 * One configuration's model catalogue, with what each model costs.
 *
 * Two ways a model gets here. `Làm mới` asks the provider what it serves and
 * replaces the discovered set; `Thêm` records one by hand, which is what a
 * gateway that does not implement `/models` needs. The `source` tag says which,
 * because a model nobody discovered is a model nobody has confirmed exists.
 */
export function ProviderModelList({ providerId }: { providerId: string }) {
  const { t } = useTranslation();
  const models = useQuery(providerModelsOptions(providerId));
  const prices = useQuery(priceRowsOptions);
  const refresh = useRefreshProviderModelsMutation();
  const addModel = useAddProviderModelMutation();
  const [manualId, setManualId] = useState('');
  const [pricing, setPricing] = useState<ModelPriceTarget>();

  const rows = models.data ?? [];
  const priceRows = prices.data ?? [];

  return (
    <div className="grid gap-3 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-body font-semibold text-ink">
          {t('lifecycle.providers.models.title', { count: rows.length })}
        </h4>
        <Button
          type="button"
          intent="neutral"
          size="small"
          loading={refresh.isPending}
          leadingIcon={<ArrowsClockwise aria-hidden className="size-4" />}
          onClick={() => refresh.mutate(providerId)}
        >
          {t('lifecycle.providers.models.refresh')}
        </Button>
      </div>

      {refresh.isError ? (
        <p role="alert" className="text-caption text-danger-text">{t('lifecycle.providers.models.refreshError')}</p>
      ) : null}

      {rows.length === 0 ? (
        <p className="text-caption text-muted">{t('lifecycle.providers.models.empty')}</p>
      ) : (
        <ul className="grid gap-2">
          {rows.map((model) => {
            const price = priceInForce(priceRows, providerId, model.model_id);
            return (
              <li key={model.model_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-subtle px-3 py-2">
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <code className="truncate text-caption text-ink">{model.model_id}</code>
                  <Tag state="neutral">{t(`lifecycle.providers.models.source.${model.source}`)}</Tag>
                  {model.available ? null : <Tag state="warning">{t('lifecycle.providers.models.unavailable')}</Tag>}
                </span>
                <span className="flex items-center gap-3">
                  {/* The floor only appears when there is one. Rendering
                      "· min 0" on every row would make the normal case look
                      like a setting somebody chose. */}
                  <span className="text-caption text-muted">
                    {price
                      ? t('lifecycle.providers.price.summary', {
                          input: price.input_price_per_1k * PRICE_UNIT_SCALE,
                          output: price.output_price_per_1k * PRICE_UNIT_SCALE,
                          currency: price.currency,
                        }) + (price.minimum_charge_per_request > 0
                          ? t('lifecycle.providers.price.minimumSummary', {
                              minimum: price.minimum_charge_per_request,
                            })
                          : '')
                      : t('lifecycle.providers.price.unset')}
                  </span>
                  <Button
                    type="button"
                    intent="neutral"
                    size="small"
                    leadingIcon={<CurrencyDollar aria-hidden className="size-4" />}
                    onClick={() => setPricing({ providerId, modelId: model.model_id, current: price })}
                  >
                    {price ? t('lifecycle.providers.price.edit') : t('lifecycle.providers.price.set')}
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {/* A gateway with no `/models` endpoint discovers nothing, and the prompt
          composer needs a name to bind to. This is that name, typed. */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <Input
            label={t('lifecycle.providers.models.addLabel')}
            placeholder={t('lifecycle.providers.models.addPlaceholder')}
            value={manualId}
            spellCheck={false}
            onChange={(event) => setManualId(event.target.value)}
          />
        </div>
        <Button
          type="button"
          intent="neutral"
          disabled={!manualId.trim()}
          loading={addModel.isPending}
          leadingIcon={<Plus aria-hidden className="size-4" />}
          onClick={() => addModel.mutate(
            { providerId, modelId: manualId.trim() },
            { onSuccess: () => setManualId('') },
          )}
        >
          {t('lifecycle.providers.models.add')}
        </Button>
      </div>
      {addModel.isError ? (
        <p role="alert" className="text-caption text-danger-text">{t('lifecycle.providers.models.addError')}</p>
      ) : null}

      <ModelPriceDialog target={pricing} onClose={() => setPricing(undefined)} />
    </div>
  );
}
