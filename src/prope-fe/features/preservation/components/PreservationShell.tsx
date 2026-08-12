import { Bell, CheckSquare, Plus, SealCheck } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { AppShell } from '@/components/AppShell';
import { buttonVariants } from '@/components/ui/buttonVariants';
import { Link } from 'react-router-dom';

export interface PreservationShellProps {
  activeId: 'prompts' | 'registry' | 'reviews';
  title: string;
  description?: string;
  showCreate?: boolean;
  children: ReactNode;
}

export function PreservationShell({ activeId, title, description, showCreate = true, children }: PreservationShellProps) {
  const { t } = useTranslation();
  const items = [
    { id: 'registry', label: t('preservation.navigation.registry'), href: '/app/registry', icon: <SealCheck aria-hidden className="size-5" /> },
    { id: 'reviews', label: t('preservation.navigation.reviews'), href: '/app/reviews', icon: <CheckSquare aria-hidden className="size-5" /> },
    { id: 'prompts', label: t('preservation.navigation.register'), href: '/app/prompts/new', icon: <Plus aria-hidden className="size-5" /> },
  ];
  const account = (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
      <span aria-hidden className="grid size-9 place-items-center rounded-full bg-hero text-caption font-semibold text-inverse">{t('preservation.account.initials')}</span>
      <div className="min-w-0"><p className="truncate text-body font-semibold text-ink">{t('preservation.account.name')}</p><p className="truncate text-caption text-muted">{t('preservation.account.role')}</p></div>
      <Bell aria-hidden className="ml-auto size-4 text-muted" />
    </div>
  );
  const action = showCreate ? (
    <Link to="/app/prompts/new" className={buttonVariants({ intent: 'primary' })}>
      <Plus aria-hidden className="size-4" />{t('preservation.actions.add')}
    </Link>
  ) : undefined;

  return <AppShell items={items} activeId={activeId} title={title} description={description} action={action} account={account}>{children}</AppShell>;
}
