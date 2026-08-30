import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { lifecycleKeys, useCreatePriceRowMutation } from '@/features/prompt-lifecycle/queries';
import {
  PRICE_UNIT_SCALE,
  type PriceRow,
  type ProviderModel,
} from '@/features/prompt-lifecycle/providerTypes';

/**
 * The models whose price the provider itself listed and whose cost the ledger
 * does not price yet.
 *
 * A model with no in-force row is unpriced; one whose published figure is
 * (0, 0) stays that way — the ledger refuses an all-zero row because it would
 * price every call at nothing, so "free" is a judgement for the rate form,
 * which can attach a per-request floor.
 */
function adoptable(
  providerId: string,
  models: ProviderModel[],
  rows: PriceRow[],
): ProviderModel[] {
  const inForce = new Set(
    rows
      .filter((row) => row.provider_config_id === providerId && row.effective_to == null)
      .map((row) => row.upstream_model),
  );
  return models.filter((model) => {
    if (inForce.has(model.model_id)) return false;
    const input = model.input_price_per_1k;
    const output = model.output_price_per_1k;
    if (input == null || output == null) return false;
    return input > 0 || output > 0;
  });
}

/**
 * One click from "the provider listed these prices" to "the ledger prices
 * them". Appends one row per model through the same `POST /prices` seam the
 * rate form uses — the table stays insert-only and the summary figures stay
 * server-owned — so this is bulk pre-filling, never a side effect of loading
 * the page.
 *
 * Discovered figures are USD per token on every catalogue that publishes
 * them; the ×1000 to per-1M is the same unit hop the form does by hand.
 */
export function useApplyDiscoveredPrices(providerId: string, models: ProviderModel[], rows: PriceRow[]) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const mutation = useCreatePriceRowMutation();
  const [applying, setApplying] = useState(false);
  const [lastApplied, setLastApplied] = useState<number>();

  const applicable = useMemo(
    () => adoptable(providerId, models, rows),
    [providerId, models, rows],
  );

  const formatRate = (per1k: number): string => String(Number((per1k * PRICE_UNIT_SCALE).toPrecision(6)));

  const discoveredSummary = (model: ProviderModel): string | undefined => {
    const input = model.input_price_per_1k;
    const output = model.output_price_per_1k;
    if (input == null || output == null) return undefined;
    return t('lifecycle.providers.price.discoveredSummary', {
      input: formatRate(input),
      output: formatRate(output),
    });
  };

  /** Per-1M figures for pre-filling the rate form when nothing is in force. */
  const discoveredSeed = (model: ProviderModel): { input: number; output: number } | undefined => {
    const input = model.input_price_per_1k;
    const output = model.output_price_per_1k;
    if (input == null || output == null) return undefined;
    return { input: input * PRICE_UNIT_SCALE, output: output * PRICE_UNIT_SCALE };
  };

  const apply = async (): Promise<void> => {
    setApplying(true);
    let applied = 0;
    for (const model of applicable) {
      const input = model.input_price_per_1k;
      const output = model.output_price_per_1k;
      if (input == null || output == null) continue;
      try {
        await mutation.mutateAsync({
          providerId,
          upstreamModel: model.model_id,
          inputPerMillion: input * PRICE_UNIT_SCALE,
          outputPerMillion: output * PRICE_UNIT_SCALE,
          minimumPerRequest: 0,
          currency: 'USD',
        });
        applied += 1;
      } catch {
        // One refused row must not stop the rest; the count reports honesty.
      }
    }
    setApplying(false);
    setLastApplied(applied);
    if (applied > 0) {
      await client.invalidateQueries({ queryKey: lifecycleKeys.prices });
    }
  };

  return {
    applicableCount: applicable.length,
    applying,
    lastApplied,
    discoveredSummary,
    discoveredSeed,
    apply,
  };
}
