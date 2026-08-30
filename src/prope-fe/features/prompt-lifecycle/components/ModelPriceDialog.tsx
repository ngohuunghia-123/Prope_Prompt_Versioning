import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { providerErrorKeys, providerErrorValues } from '@/features/prompt-lifecycle/providerErrors';
import { PRICE_UNIT_SCALE, type PriceRow } from '@/features/prompt-lifecycle/providerTypes';
import { useCreatePriceRowMutation } from '@/features/prompt-lifecycle/queries';

export interface ModelPriceTarget {
  providerId: string;
  modelId: string;
  /** The row currently in force, if there is one. Seeds the two fields. */
  current?: PriceRow;
  /** What the provider itself listed, per 1M, when no row is in force. */
  discovered?: { input: number; output: number };
}

/**
 * Set what one model costs.
 *
 * Vendors publish per-1M rates and `ledger.price_table` stores per-1k, so the
 * form takes per-1M and `createPriceRow` divides. Doing it at the API edge means
 * every figure on screen is in the unit the rate card is written in and exactly
 * one line knows about the other.
 *
 * **This appends, it never edits.** A-102 makes the table insert-only so that a
 * cost recorded months ago stays explicable under the price that produced it —
 * so the copy says "from now on" rather than "change", and the superseded row
 * keeps existing behind this one.
 */
export function ModelPriceDialog({ target, onClose }: { target: ModelPriceTarget | undefined; onClose: () => void }) {
  const { t } = useTranslation();
  const mutation = useCreatePriceRowMutation();
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [minimum, setMinimum] = useState('0');
  const [currency, setCurrency] = useState('USD');

  useEffect(() => {
    if (!target) return;
    const current = target.current;
    const seed = current
      ? { input: current.input_price_per_1k * PRICE_UNIT_SCALE, output: current.output_price_per_1k * PRICE_UNIT_SCALE }
      : target.discovered;
    setInput(seed ? String(seed.input) : '');
    setOutput(seed ? String(seed.output) : '');
    // Seeded at '0' rather than blank: no floor is the normal case, and an
    // empty required field on a row that is about to be superseded reads as a
    // figure somebody forgot rather than as the absence it is.
    setMinimum(current ? String(current.minimum_charge_per_request) : '0');
    setCurrency(current?.currency ?? 'USD');
    mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const inputPrice = Number(input);
  const outputPrice = Number(output);
  const minimumPrice = Number(minimum);
  // `ck_price_table_prices_are_non_negative` permits (0, 0) — a free tier is a
  // real price — so the only refusals here are blank, non-numeric and negative.
  //
  // All three at zero IS refused, by the server: such a row would price every
  // call at exactly zero and `ck_call_record_cost_is_never_zero` would then
  // discard the whole batch. It is checked here too so the refusal arrives
  // while the figures are still on screen rather than as a 422 afterwards.
  const allZero = inputPrice === 0 && outputPrice === 0 && minimumPrice === 0;
  const valid =
    input.trim() !== '' && output.trim() !== '' && minimum.trim() !== ''
    && Number.isFinite(inputPrice) && Number.isFinite(outputPrice) && Number.isFinite(minimumPrice)
    && inputPrice >= 0 && outputPrice >= 0 && minimumPrice >= 0
    && !allZero
    && /^[A-Z]{3}$/.test(currency);

  return (
    <Modal
      open={target !== undefined}
      title={t('lifecycle.providers.price.title', { model: target?.modelId ?? '' })}
      description={t('lifecycle.providers.price.description')}
      confirmLabel={t('lifecycle.providers.price.save')}
      confirmDisabled={!valid}
      confirmLoading={mutation.isPending}
      className="max-h-[90vh] max-w-md overflow-y-auto"
      onClose={onClose}
      onConfirm={() => {
        if (!target || !valid) return;
        mutation.mutate(
          {
            providerId: target.providerId,
            upstreamModel: target.modelId,
            inputPerMillion: inputPrice,
            outputPerMillion: outputPrice,
            minimumPerRequest: minimumPrice,
            currency,
          },
          { onSuccess: () => onClose() },
        );
      }}
    >
      <div className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label={t('lifecycle.providers.price.input')}
            hint={t('lifecycle.providers.price.unit', { currency })}
            inputMode="decimal"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <Input
            label={t('lifecycle.providers.price.output')}
            hint={t('lifecycle.providers.price.unit', { currency })}
            inputMode="decimal"
            value={output}
            onChange={(event) => setOutput(event.target.value)}
          />
        </div>
        {/* Per request, so its unit line says so — the two fields above are per
            1M tokens and a floor sharing their row would read as a third rate. */}
        <Input
          label={t('lifecycle.providers.price.minimum')}
          hint={t('lifecycle.providers.price.minimumHint', { currency })}
          inputMode="decimal"
          value={minimum}
          onChange={(event) => setMinimum(event.target.value)}
        />
        <Input
          label={t('lifecycle.providers.price.currency')}
          hint={t('lifecycle.providers.price.currencyHint')}
          value={currency}
          maxLength={3}
          onChange={(event) => setCurrency(event.target.value.toUpperCase())}
        />
        {mutation.isError ? (
          <p role="alert" className="text-caption text-danger-text">
            {t(providerErrorKeys(mutation.error), providerErrorValues(mutation.error))}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
