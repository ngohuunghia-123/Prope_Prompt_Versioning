import { BracketsCurly, Database, LockKey, UserCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import type { PromptDetail } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { RevisionBindingDisplay } from '@/features/prompt-lifecycle/components/RevisionBindingDisplay';
import { useWorkspaceAccountIdentity } from '@/features/auth/components/useWorkspaceAccountIdentity';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';

export interface PromptContentPanelProps { prompt: PromptDetail; revisionId: string; }

export function PromptContentPanel({ prompt, revisionId }: PromptContentPanelProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();
  const account = useWorkspaceAccountIdentity();
  const { userName } = useWorkspaceDisplayNames();
  const revision = prompt.revisions.find((item) => item.id === revisionId) ?? prompt.revisions[0];
  if (!revision) return null;
  return (
    <section aria-labelledby="prompt-content-title" className="grid gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-overline font-bold tracking-navigation-overline text-navigation-overline uppercase">{t('lifecycle.overview.content.eyebrow', { revision: revision.number })}</p><h2 id="prompt-content-title" className="mt-2 font-display text-heading-2 text-ink">{prompt.title}</h2><p className="mt-2 text-body text-muted">{prompt.purpose}</p></div><StatusBadge tone={revision.status === 'retired' ? 'disabled' : 'active'}>{t(`status.${revision.status}`)}</StatusBadge></header>
      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-border bg-subtle p-4"><dt className="flex items-center gap-2 text-caption text-muted"><Database aria-hidden className="size-4" />{t('lifecycle.detail.provider')}</dt><dd className="mt-2"><RevisionBindingDisplay revision={revision} /></dd></div>
        <div className="rounded-xl border border-border bg-subtle p-4"><dt className="flex items-center gap-2 text-caption text-muted"><BracketsCurly aria-hidden className="size-4" />{t('lifecycle.editor.modelName')}</dt><dd className="mt-2 text-body font-medium text-ink">{prompt.modelName}</dd></div>
        <div className="rounded-xl border border-border bg-subtle p-4"><dt className="flex items-center gap-2 text-caption text-muted"><UserCircle aria-hidden className="size-4" />{t('lifecycle.overview.content.owner')}</dt><dd className="mt-2 text-body font-medium text-ink">{prompt.owner === account.session.data?.user.id ? account.name : userName(prompt.owner)}</dd></div>
        <div className="rounded-xl border border-border bg-subtle p-4"><dt className="flex items-center gap-2 text-caption text-muted"><LockKey aria-hidden className="size-4" />{t('lifecycle.editor.access')}</dt><dd className="mt-2 text-body font-medium text-ink">{t(`lifecycle.access.${prompt.access}`)}</dd></div>
      </dl>
      <div><h3 className="font-display text-heading-3 text-ink">{t('lifecycle.editor.promptBody')}</h3><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-subtle p-4 font-mono text-caption text-ink">{prompt.promptBody}</pre></div>
      <div className="grid gap-4 sm:grid-cols-2"><div><h3 className="text-body font-semibold text-ink">{t('lifecycle.detail.fallback')}</h3><p className="mt-2 rounded-xl border border-border bg-subtle p-4 text-body text-muted">{prompt.fallbackAnswer}</p></div><div><h3 className="text-body font-semibold text-ink">{t('lifecycle.overview.content.revisionMetadata')}</h3><p className="mt-2 rounded-xl border border-border bg-subtle p-4 text-body text-muted">{revision.summary}<span className="mt-2 block text-caption">{userName(revision.author)} · {format.date(revision.createdAt)}</span></p></div></div>
    </section>
  );
}
