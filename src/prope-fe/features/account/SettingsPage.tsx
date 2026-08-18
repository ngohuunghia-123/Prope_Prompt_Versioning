import { CaretRight, Key, PlugsConnected, UserCircle, UsersThree } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Card } from '@/components/Card';
import { PageIntro } from '@/features/prompt-lifecycle/components/PageIntro';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { sessionOptions } from '@/features/auth/queries';

/** A settings row that is really a doorway to the screen that owns the thing. */
function SettingsLink({ to, icon, title, body, }: { to: string; icon: ReactNode; title: string; body: string }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-4 rounded-xl border border-border bg-surface p-4 transition-colors duration-(--prope-motion-duration-fast) hover:border-primary focus-visible:outline-2 focus-visible:outline-focus"
    >
      <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-lg bg-subtle text-secondary">{icon}</span>
      <span className="min-w-0 flex-1">
        <strong className="block text-body font-semibold text-ink">{title}</strong>
        <span className="block text-caption text-muted">{body}</span>
      </span>
      <CaretRight aria-hidden className="size-4 shrink-0 text-muted" />
    </Link>
  );
}

/**
 * Workspace settings.
 *
 * What this deliberately does *not* contain: a language picker, notification
 * preferences, an editable workspace name, and a second API-key form. There was
 * an unrouted `SettingsPanel` holding all four, every one of them a control
 * wired to `onChange={() => {}}` — and its API-key screen kept its own mock
 * provider list, which would have sat beside the real `provider_access` page
 * showing different providers. ADR-0053 also makes the interface
 * Vietnamese-only for the MVP, so a language switcher would contradict it.
 *
 * So this page shows the workspace facts the session already proves, and hands
 * off to the screens that genuinely own the rest. It grows when there is an
 * endpoint behind a control, not before.
 */
export function SettingsPage() {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);

  if (session.isPending) return <QueryState state="loading" />;
  if (session.isError) return <QueryState state="error" onRetry={() => void session.refetch()} />;
  if (!session.data) return <QueryState state="empty" />;

  const { user } = session.data;

  return (
    <div className="mx-auto grid w-full max-w-(--container-content) gap-6">
      <PageIntro
        eyebrow={t('settings.page.eyebrow')}
        title={t('settings.page.title')}
        description={t('settings.page.description')}
      />

      <Card title={t('settings.workspace.info')}>
        <dl className="mt-2 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-subtle p-4">
            <dt className="flex items-center gap-2 text-caption text-muted">
              <UsersThree aria-hidden className="size-4" />
              {t('settings.workspace.name')}
            </dt>
            <dd className="mt-2 truncate text-body font-medium text-ink">{user.workspaceName}</dd>
          </div>
          <div className="rounded-xl border border-border bg-subtle p-4">
            <dt className="flex items-center gap-2 text-caption text-muted">
              <UserCircle aria-hidden className="size-4" />
              {t('settings.page.yourRole')}
            </dt>
            <dd className="mt-2 text-body font-medium text-ink">{t(`roles.${user.role}`)}</dd>
          </div>
        </dl>
        {/* Renaming a workspace and managing members have no endpoint yet, and a
            field that accepts a change it cannot save is worse than none. */}
        <p className="mt-4 text-caption text-muted">{t('settings.page.workspaceReadOnly')}</p>
      </Card>

      <Card title={t('settings.page.elsewhere')}>
        <div className="mt-2 grid gap-3">
          <SettingsLink
            to="/app/settings/providers"
            icon={<PlugsConnected className="size-5" />}
            title={t('settings.page.providers.title')}
            body={t('settings.page.providers.body')}
          />
          <SettingsLink
            to="/app/settings/keys"
            icon={<Key className="size-5" />}
            title={t('settings.page.keys.title')}
            body={t('settings.page.keys.body')}
          />
          <SettingsLink
            to="/app/account"
            icon={<UserCircle className="size-5" />}
            title={t('settings.page.account.title')}
            body={t('settings.page.account.body')}
          />
        </div>
      </Card>
    </div>
  );
}
