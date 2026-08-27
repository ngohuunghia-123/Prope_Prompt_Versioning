import { Plus } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { RouterComboEntryRow } from '@/features/prompt-lifecycle/components/RouterComboEntryRow';
import {
  providerConfigsOptions,
  useCreateRouterComboMutation,
  useReplaceRouterComboMutation,
} from '@/features/prompt-lifecycle/queries';
import { isRoutingUnavailable } from '@/features/prompt-lifecycle/routerComboApi';
import {
  MAX_COMBO_ENTRIES,
  MIN_COMBO_ENTRIES,
  isRouterComboErrorCode,
  type RouterCombo,
  type RouterComboEntryInput,
} from '@/features/prompt-lifecycle/routerComboTypes';
import { isApiError } from '@/lib/apiClient';

const UNSET = '';

function errorKey(error: unknown): string {
  if (isRoutingUnavailable(error)) return 'lifecycle.router.error.mockMode';
  if (isApiError(error) && isRouterComboErrorCode(error.code)) return `lifecycle.router.error.${error.code}`;
  if (isApiError(error) && error.code === 'permission_denied') return 'lifecycle.router.error.permission_denied';
  return 'lifecycle.router.error.unknown';
}

function blankEntries(): RouterComboEntryInput[] {
  // Two, because two is the minimum a combo can be saved with. Opening on one
  // row and refusing the save is a rule the person meets only after typing.
  return [
    { providerConfigId: UNSET, upstreamModel: UNSET },
    { providerConfigId: UNSET, upstreamModel: UNSET },
  ];
}

function key(entry: RouterComboEntryInput): string {
  return `${entry.providerConfigId}\u0000${entry.upstreamModel}`;
}

/**
 * Create or edit one router combo — ADR-0069.
 *
 * `combo` absent is create; present is edit. `PUT` replaces the whole list,
 * which is why editing loads the rungs into local state and sends all of them
 * back: the rungs are ordered, and patching an ordered list is how orders get
 * corrupted.
 *
 * The dialog states the snapshot rule and states the half of it that belongs
 * here: an edit changes what the **next** revision copies, and changes nothing
 * already released. The delete confirmation on the page states the other half.
 * Both are needed — somebody who reads only one of them draws the wrong
 * conclusion about the other.
 */
export function RouterComboDialog({ open, combo, onClose, onSaved }: {
  open: boolean;
  combo?: RouterCombo;
  onClose: () => void;
  onSaved?: (combo: RouterCombo) => void;
}) {
  const { t } = useTranslation();
  const configs = useQuery(providerConfigsOptions);
  const create = useCreateRouterComboMutation();
  const replace = useReplaceRouterComboMutation();
  const mutation = combo ? replace : create;

  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [entries, setEntries] = useState<RouterComboEntryInput[]>(blankEntries);

  // Reset on every open, from whichever combo is being edited. Same rule the
  // provider dialog keeps: a dialog that reopens holding the last attempt is a
  // dialog that submits it by accident.
  useEffect(() => {
    if (!open) return;
    setDisplayName(combo?.display_name ?? '');
    setDescription(combo?.description ?? '');
    setEntries(
      combo
        ? combo.entries.map((entry) => ({
            providerConfigId: entry.provider_config_id,
            upstreamModel: entry.upstream_model,
          }))
        : blankEntries(),
    );
    create.reset();
    replace.reset();
    // `create`/`replace` change identity on every state transition of the
    // request, and depending on them would re-clear the form mid-submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, combo]);

  const providers = configs.data ?? [];

  // Which rungs repeat a `(provider, model)` pair that appeared earlier. The
  // server refuses the whole list on `uq_router_combo_entry_target`; marking
  // the second one is what makes that a message about the row somebody just
  // filled in. The same provider with a DIFFERENT model is not a duplicate — a
  // cheaper model on a key that already works is one of the two things this
  // feature is for.
  const seen = new Set<string>();
  const duplicates = entries.map((entry) => {
    if (entry.providerConfigId === UNSET || entry.upstreamModel === UNSET) return false;
    const identity = key(entry);
    if (seen.has(identity)) return true;
    seen.add(identity);
    return false;
  });

  const whole = entries.every((entry) => entry.providerConfigId !== UNSET && entry.upstreamModel !== UNSET);
  const complete = displayName.trim().length > 0
    && entries.length >= MIN_COMBO_ENTRIES
    && entries.length <= MAX_COMBO_ENTRIES
    && whole
    && !duplicates.some(Boolean);

  const move = (index: number, direction: -1 | 1) => {
    setEntries((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      const [moved] = next.splice(index, 1);
      if (moved) next.splice(target, 0, moved);
      return next;
    });
  };

  return (
    <Modal
      open={open}
      title={combo ? t('lifecycle.router.dialog.editTitle') : t('lifecycle.router.dialog.createTitle')}
      description={combo ? t('lifecycle.router.dialog.editDescription') : t('lifecycle.router.dialog.createDescription')}
      confirmLabel={combo ? t('lifecycle.router.dialog.save') : t('lifecycle.router.createAction')}
      confirmDisabled={!complete}
      confirmLoading={mutation.isPending}
      className="max-h-[90vh] max-w-lg overflow-y-auto"
      onClose={onClose}
      onConfirm={() => {
        if (!complete) return;
        const input = { displayName: displayName.trim(), description: description.trim(), entries };
        const settle = { onSuccess: (saved: RouterCombo) => { onSaved?.(saved); onClose(); } };
        if (combo) replace.mutate({ comboId: combo.combo_id, ...input }, settle);
        else create.mutate(input, settle);
      }}
    >
      <div className="grid gap-4">
        <Input
          label={t('lifecycle.router.dialog.name')}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <Textarea
          label={t('lifecycle.router.dialog.description')}
          hint={t('lifecycle.router.dialog.descriptionHint')}
          rows={2}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <div className="grid gap-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-body font-medium text-ink">{t('lifecycle.router.dialog.entries')}</span>
            <span className="text-caption text-muted">{t('lifecycle.router.dialog.entriesHint')}</span>
          </div>

          <ol className="grid gap-3">
            {entries.map((entry, index) => (
              <RouterComboEntryRow
                // Index is the identity here on purpose: a rung has no id, and
                // the rows ARE positions — reordering is meant to move the DOM
                // node's content, not the node.
                key={index}
                index={index}
                total={entries.length}
                entry={entry}
                providers={providers}
                duplicate={duplicates[index] ?? false}
                onChange={(next) => setEntries((current) => current.map((item, at) => (at === index ? next : item)))}
                onMove={(direction) => move(index, direction)}
                onRemove={() => setEntries((current) => current.filter((_item, at) => at !== index))}
              />
            ))}
          </ol>

          <div>
            <Button
              type="button"
              intent="neutral"
              size="small"
              leadingIcon={<Plus aria-hidden className="size-4" />}
              disabled={entries.length >= MAX_COMBO_ENTRIES}
              onClick={() => setEntries((current) => [...current, { providerConfigId: UNSET, upstreamModel: UNSET }])}
            >
              {t('lifecycle.router.dialog.addEntry')}
            </Button>
          </div>

          {entries.length < MIN_COMBO_ENTRIES ? (
            <p className="text-caption text-muted">{t('lifecycle.router.dialog.tooFew', { count: MIN_COMBO_ENTRIES })}</p>
          ) : null}
        </div>

        {/* Half of the snapshot rule. The other half is on the delete confirm,
            and neither is enough on its own. */}
        <p className="rounded-control bg-subtle px-3 py-2 text-caption text-muted">
          {combo && combo.revision_count > 0
            ? t('lifecycle.router.snapshot.editBound', { count: combo.revision_count })
            : t('lifecycle.router.snapshot.edit')}
        </p>

        {mutation.isError ? (
          <p role="alert" className="text-caption text-danger-text">{t(errorKey(mutation.error))}</p>
        ) : null}
      </div>
    </Modal>
  );
}
