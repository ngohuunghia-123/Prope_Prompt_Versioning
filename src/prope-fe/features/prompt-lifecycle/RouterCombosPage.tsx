import { PencilSimple, PlugsConnected, Trash, TreeStructure } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { RouterComboDialog } from '@/features/prompt-lifecycle/components/RouterComboDialog';
import { RouterComboSummary } from '@/features/prompt-lifecycle/components/RouterComboSummary';
import {
  providerConfigsOptions,
  routerCombosOptions,
  useDeleteRouterComboMutation,
} from '@/features/prompt-lifecycle/queries';
import type { RouterCombo } from '@/features/prompt-lifecycle/routerComboTypes';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';

/**
 * One combo.
 *
 * `revision_count` is the headline figure and it is not a blocker: deleting a
 * combo bound to forty revisions is allowed, because each of those revisions
 * holds its own frozen copy and keeps serving. The number is here so that the
 * sentence "editing this changes nothing already released" has something
 * concrete standing behind it.
 */
function RouterComboCard({ combo, onEdit, onDelete }: {
  combo: RouterCombo;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const configs = useQuery(providerConfigsOptions);
  const providers = configs.data ?? [];

  // A rung pointing at a provider that is disabled, unverified, or gone. Worth
  // a warning on the card rather than only inside the dialog: the first rung
  // degrading silently is exactly the failure this feature is supposed to
  // prevent, and nobody opens an edit dialog to check.
  const unusable = combo.entries.filter((entry) => {
    const provider = providers.find((candidate) => candidate.provider_config_id === entry.provider_config_id);
    return provider === undefined || provider.status === 'disabled' || provider.verification_status !== 'passed';
  });

  return (
    <Card title={combo.display_name}>
      <div className="mt-2 grid gap-3">
        {combo.description ? <p className="text-caption text-muted">{combo.description}</p> : null}

        <RouterComboSummary entries={combo.entries} />

        {unusable.length > 0 && !configs.isPending ? (
          <p role="status" className="rounded-lg border border-warning-strong bg-warning px-3 py-2 text-caption text-warning-text">
            {t('lifecycle.router.card.unusable', { count: unusable.length })}
          </p>
        ) : null}

        <dl className="grid gap-1 text-caption">
          <div className="flex flex-wrap gap-2">
            <dt className="text-muted">{t('lifecycle.router.card.boundRevisions')}</dt>
            <dd className="text-ink">{combo.revision_count}</dd>
          </div>
          <div className="flex flex-wrap gap-2">
            <dt className="text-muted">{t('lifecycle.router.card.updated')}</dt>
            <dd className="text-ink">{format.date(combo.updated_at)}</dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-2">
          <Button type="button" intent="neutral" size="small" leadingIcon={<PencilSimple aria-hidden className="size-4" />} onClick={onEdit}>
            {t('lifecycle.router.card.edit')}
          </Button>
          <Button type="button" intent="neutral" size="small" leadingIcon={<Trash aria-hidden className="size-4" />} onClick={onDelete}>
            {t('lifecycle.router.card.delete')}
          </Button>
        </div>
      </div>
    </Card>
  );
}

/**
 * Router combos — ADR-0069's settings destination.
 *
 * A combo is an ordered list of `(provider, model)` rungs that a revision can
 * bind to instead of a single pair. When the first rung refuses in a way
 * another provider could answer, the gateway tries the next one inside the same
 * request deadline.
 *
 * Nothing on this page reaches production on its own. Binding a prompt to a
 * combo happens in the composer and goes through the same review as any other
 * change, which is what keeps A-024 true and the approval record honest.
 */
export function RouterCombosPage() {
  const { t } = useTranslation();
  const query = useQuery(routerCombosOptions);
  const configs = useQuery(providerConfigsOptions);
  const remove = useDeleteRouterComboMutation();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<RouterCombo>();
  const [deleting, setDeleting] = useState<RouterCombo>();

  const combos = query.data ?? [];
  const providers = configs.data ?? [];
  // Two empty states, not one. Offering "create a combo" to a workspace with no
  // providers is a button that opens a dialog that cannot be saved.
  //
  // ZERO is the bar, not two: a combo needs two ENTRIES and two entries may be two
  // models on the same provider, which is a legitimate rung (a cheaper model on the
  // same key). Gating on two providers would refuse the single-provider workspace a
  // combo the server would have accepted.
  const noProviders = !configs.isPending && !configs.isError && providers.length === 0;

  const openCreate = () => { setEditing(undefined); setDialogOpen(true); };
  const openEdit = (combo: RouterCombo) => { setEditing(combo); setDialogOpen(true); };

  return (
    <div className="grid gap-6">
      <PageIntro
        eyebrow={t('lifecycle.router.eyebrow')}
        title={t('lifecycle.router.title')}
        description={t('lifecycle.router.description')}
        action={
          <Button
            type="button"
            leadingIcon={<TreeStructure aria-hidden className="size-4" />}
            disabled={noProviders}
            onClick={openCreate}
          >
            {t('lifecycle.router.createAction')}
          </Button>
        }
      />

      {query.isPending ? <QueryState state="loading" loadingLayout="table" /> : null}
      {query.isError ? <QueryState state="error" onRetry={() => void query.refetch()} /> : null}

      {!query.isPending && !query.isError && combos.length === 0 && noProviders ? (
        <div className="grid gap-3 justify-items-center">
          <QueryState
            state="empty"
            titleOverride={t('lifecycle.router.empty.noProvidersTitle')}
            descriptionOverride={t('lifecycle.router.empty.noProvidersBody')}
          />
          <Link to="/app/settings/providers">
            <Button type="button" intent="neutral" size="small" leadingIcon={<PlugsConnected aria-hidden className="size-4" />}>
              {t('lifecycle.router.empty.manageProviders')}
            </Button>
          </Link>
        </div>
      ) : null}

      {!query.isPending && !query.isError && combos.length === 0 && !noProviders ? (
        <QueryState
          state="empty"
          titleOverride={t('lifecycle.router.empty.title')}
          descriptionOverride={t('lifecycle.router.empty.body')}
        />
      ) : null}

      {combos.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {combos.map((combo) => (
            <RouterComboCard
              key={combo.combo_id}
              combo={combo}
              onEdit={() => openEdit(combo)}
              onDelete={() => setDeleting(combo)}
            />
          ))}
        </div>
      ) : null}

      <RouterComboDialog
        open={dialogOpen}
        combo={editing}
        onClose={() => { setDialogOpen(false); setEditing(undefined); }}
      />

      {/* The other half of the snapshot rule, and the reason this delete is not
          destructive in the way the provider delete is: every revision made
          from this template keeps its own frozen copy and keeps serving. What
          is lost is the ability to bind a NEW revision to it. */}
      <Modal
        open={deleting !== undefined}
        destructive
        title={t('lifecycle.router.deleteTitle')}
        description={t('lifecycle.router.deleteDescription', { name: deleting?.display_name ?? '' })}
        confirmLabel={t('lifecycle.router.card.delete')}
        confirmLoading={remove.isPending}
        onClose={() => setDeleting(undefined)}
        onConfirm={() => {
          if (!deleting) return;
          remove.mutate(deleting.combo_id, { onSuccess: () => setDeleting(undefined) });
        }}
      >
        <div className="grid gap-2">
          <p className="text-caption text-muted">
            {t('lifecycle.router.snapshot.delete', { count: deleting?.revision_count ?? 0 })}
          </p>
          {remove.isError ? (
            <p role="alert" className="text-caption text-danger-text">{t('lifecycle.router.error.unknown')}</p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}
