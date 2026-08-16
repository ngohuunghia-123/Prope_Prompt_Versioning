import { ClockCounterClockwise, Database, FolderOpen, FolderPlus, GearSix, Key, MagnifyingGlass, PlugsConnected, TerminalWindow, UserCircle } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import type { BreadcrumbItem } from '@/components/TopBar';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Tabs } from '@/components/Tabs';
import { WorkspaceAccount } from '@/features/auth/components/WorkspaceAccount';
import { WorkspaceCompactAccount } from '@/features/auth/components/WorkspaceCompactAccount';
import { PromptLifecycleRoutes } from '@/features/prompt-lifecycle/PromptLifecycleRoutes';
import { FolderFormDialog } from '@/features/prompt-lifecycle/components/FolderFormDialog';
import { NAVIGATION_ID_BY_SECTION, useLifecycleNavigation } from '@/features/prompt-lifecycle/useLifecycleNavigation';
import { useDashboardContext } from '@/components/DashboardToolbarContext';

function humanizeSlug(value: string) {
  return value.split('-').map((part) => part ? `${part[0]?.toUpperCase()}${part.slice(1)}` : '').join(' ');
}

export function WorkspacePage() {
  const { t } = useTranslation();
  const { pathname, state } = useLocation();
  const navigate = useNavigate();
  const items = useLifecycleNavigation();
  const { setToolbarNode, filters } = useDashboardContext();
  const [isCreateFolderOpen, setIsCreateFolderOpen] = useState(false);
  const segments = pathname.split('/').filter(Boolean).slice(1);
  const [section = 'prompts', resourceId, child] = segments;
  // Which sidebar entry reads as current. A section with no entry — an unknown
  // path on its way to the catch-all — falls back to the registry rather than
  // leaving every item unhighlighted.
  const activeId = NAVIGATION_ID_BY_SECTION[section] ?? 'registry/prompts';
  const sectionKey = ['prompts', 'search', 'reviews', 'datasets', 'providers', 'playground', 'keys', 'settings', 'account'].includes(section) ? section : 'prompts';
  const sectionTitle = t(`workspace.sections.${sectionKey}.title`);
  const sectionIcon = section === 'reviews' ? <ClockCounterClockwise className="size-4" />
    : section === 'playground' ? <TerminalWindow className="size-4" />
    : section === 'keys' ? <Key className="size-4" />
    : section === 'providers' ? <PlugsConnected className="size-4" />
    : section === 'datasets' ? <Database className="size-4" />
    : section === 'search' ? <MagnifyingGlass className="size-4" />
    : section === 'settings' ? <GearSix className="size-4" />
    : section === 'account' ? <UserCircle className="size-4" />
    : <FolderOpen className="size-4" />;
  let breadcrumbs: BreadcrumbItem[] = [{ label: sectionTitle, icon: sectionIcon }];
  let tabs: ReactNode | undefined;

  // Search/filter toolbar on the prompts dashboard only
  const isDashboard = section === 'prompts' && !resourceId;
  const statusOptions = useMemo(() => [
    { value: 'all', label: t('registry.all') },
    { value: 'draft', label: t('status.draft') },
    { value: 'inReview', label: t('status.inReview') },
    { value: 'approved', label: t('status.approved') },
    { value: 'inUse', label: t('status.inUse') },
  ], [t]);

  const toolbarContent = useMemo(() => isDashboard ? (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
      <div className="min-w-48 flex-1 sm:min-w-64">
        <Input
          label={t('registry.search')}
          labelHidden
          value={filters.search}
          onChange={(e) => filters.setSearch(e.target.value)}
          placeholder={t('registry.searchPlaceholder')}
          type="search"
          name="prompt-search"
        />
      </div>
      <Select
        label={t('registry.filter')}
        options={statusOptions}
        value={filters.status}
        onValueChange={filters.setStatus}
      />
    </div>
  ) : null, [filters, isDashboard, statusOptions, t]);

  // Write toolbar to the AppShell's TopBar on mount; clean up on unmount
  useEffect(() => {
    setToolbarNode(toolbarContent);
  }, [toolbarContent, setToolbarNode]);

  if (section === 'prompts' && resourceId === 'folder' && child) {
    // /prompts/folder/<namespace> — the folder slug is the registry namespace.
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: humanizeSlug(decodeURIComponent(child)) }];
  } else if (section === 'prompts' && resourceId === 'new') {
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: t('lifecycle.newPrompt.untitled') }];
  } else if (section === 'prompts' && resourceId) {
    const editing = child === 'edit' || (child === 'revisions');
    const navigationState = state as { promptDraft?: { title?: unknown }; promptTitle?: unknown } | null;
    const promptDraft = navigationState?.promptDraft;
    const promptLabel = typeof navigationState?.promptTitle === 'string'
      ? navigationState.promptTitle
      : (child === 'test' || child === 'evaluation') && typeof promptDraft?.title === 'string'
        ? promptDraft.title
        : humanizeSlug(resourceId);
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: promptLabel, href: editing ? `/app/prompts/${resourceId}` : undefined }, ...(editing ? [{ label: t('lifecycle.editor.editTitle') }] : [])];
    const isDetailView = !editing && child !== 'playground' && child !== 'test' && child !== 'evaluation';
    if (!isDetailView && editing) {
      tabs = (
        <Tabs
          items={[
            { value: 'overview', label: t('lifecycle.editor.overviewTab') },
            { value: 'editor', label: t('lifecycle.editor.editorTab') },
          ]}
          value="editor"
          onValueChange={(value) => void navigate(value === 'overview' ? `/app/prompts/${resourceId}` : `/app/prompts/${resourceId}/edit`)}
          label={t('common.contextNavigation')}
        />
      );
    }
  } else if (section === 'reviews' && resourceId) {
    breadcrumbs = [{ label: sectionTitle, href: '/app/reviews', icon: sectionIcon }, { label: humanizeSlug(resourceId) }];
  } else if (section === 'releases' && resourceId) {
    breadcrumbs = [{ label: t('workspace.sections.prompts.title'), href: '/app/prompts', icon: <FolderOpen className="size-4" /> }, { label: t('lifecycle.overview.tabs.release') }, { label: resourceId }];
  }

  return (
    <AppShell
      items={items}
      activeId={activeId}
      breadcrumbs={breadcrumbs}
      contextNavigation={tabs}
      action={isDashboard ? (
        <Button
          type="button"
          leadingIcon={<FolderPlus aria-hidden className="size-4" />}
          onClick={() => setIsCreateFolderOpen(true)}
        >
          {t('lifecycle.folders.newFolder')}
        </Button>
      ) : undefined}
      account={<WorkspaceAccount />}
      compactAccount={<WorkspaceCompactAccount />}
    >
      <PromptLifecycleRoutes />
      <FolderFormDialog open={isCreateFolderOpen} onClose={() => setIsCreateFolderOpen(false)} />
    </AppShell>
  );
}
