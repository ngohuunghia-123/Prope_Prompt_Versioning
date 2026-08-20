import { ClockCounterClockwise, Database, FolderOpen, FolderPlus, GearSix, Key, MagnifyingGlass, PlugsConnected, TerminalWindow, UserCircle, UsersThree } from '@phosphor-icons/react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import type { BreadcrumbItem } from '@/components/TopBar';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Tabs } from '@/components/Tabs';
import type { TabItem } from '@/components/Tabs';
import { WorkspaceAccount } from '@/features/auth/components/WorkspaceAccount';
import { WorkspaceCompactAccount } from '@/features/auth/components/WorkspaceCompactAccount';
import { PromptLifecycleRoutes } from '@/features/prompt-lifecycle/PromptLifecycleRoutes';
import { FolderFormDialog } from '@/features/prompt-lifecycle/components/FolderFormDialog';
import { NAVIGATION_ID_BY_SECTION, useLifecycleNavigation } from '@/features/prompt-lifecycle/useLifecycleNavigation';
import { foldersOptions, promptOptions } from '@/features/prompt-lifecycle/queries';
import { useDashboardContext } from '@/components/DashboardToolbarContext';
import { useSettingsNavigation } from '@/features/workspace/useSettingsNavigation';

function humanizeSlug(value: string) {
  return value.split('-').map((part) => part ? `${part[0]?.toUpperCase()}${part.slice(1)}` : '').join(' ');
}

export function WorkspacePage() {
  const { t } = useTranslation();
  const { pathname, state } = useLocation();
  const navigate = useNavigate();
  const lifecycleItems = useLifecycleNavigation();
  const settingsItems = useSettingsNavigation();
  const { setToolbarNode, filters } = useDashboardContext();
  const [isCreateFolderOpen, setIsCreateFolderOpen] = useState(false);
  const segments = pathname.split('/').filter(Boolean).slice(1);
  const [section = 'prompts', resourceId, child, grandchild] = segments;
  const promptResourceId = section === 'prompts'
    && resourceId !== undefined
    && resourceId !== 'folder'
    && resourceId !== 'new'
    ? resourceId
    : '';
  const promptQuery = useQuery({ ...promptOptions(promptResourceId), enabled: promptResourceId !== '' });
  const foldersQuery = useQuery({ ...foldersOptions, enabled: section === 'prompts' });
  // Which sidebar entry reads as current. A section with no entry — an unknown
  // path on its way to the catch-all — falls back to the registry rather than
  // leaving every item unhighlighted.
  const isSettings = section === 'settings';
  const settingsSection = ['profile', 'keys', 'providers', 'workspace'].includes(resourceId ?? '') ? resourceId : 'profile';
  const items = isSettings ? settingsItems : lifecycleItems;
  const activeId = isSettings ? `settings/${settingsSection}` : NAVIGATION_ID_BY_SECTION[section] ?? 'registry/prompts';
  const activeSettingsItem = isSettings ? settingsItems.find((item) => item.id === activeId) : undefined;
  const sectionKey = ['prompts', 'search', 'reviews', 'datasets', 'providers', 'playground', 'keys', 'workspace', 'settings', 'account'].includes(section) ? section : 'prompts';
  const sectionTitle = t(`workspace.sections.${sectionKey}.title`);
  const sectionIcon = section === 'reviews' ? <ClockCounterClockwise className="size-4" />
    : section === 'playground' ? <TerminalWindow className="size-4" />
    : section === 'keys' ? <Key className="size-4" />
    : section === 'providers' ? <PlugsConnected className="size-4" />
    : section === 'datasets' ? <Database className="size-4" />
    : section === 'search' ? <MagnifyingGlass className="size-4" />
    : section === 'settings' ? <GearSix className="size-4" />
    : section === 'account' ? <UserCircle className="size-4" />
    : section === 'workspace' ? <UsersThree className="size-4" />
    : <FolderOpen className="size-4" />;
  let breadcrumbs: BreadcrumbItem[] = activeSettingsItem
    ? [{ label: activeSettingsItem.label }]
    : [{ label: sectionTitle, icon: sectionIcon }];
  let tabs: ReactNode | undefined;
  let topBarTabs: TabItem[] | undefined;
  let activeTopBarTab: string | undefined;
  let onTopBarTabChange: ((value: string) => void) | undefined;
  const isPromptDetail = section === 'prompts'
    && resourceId !== undefined
    && resourceId !== 'folder'
    && grandchild === undefined
    && (child === undefined || ['release', 'logs', 'production', 'evaluation'].includes(child));

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
    const folderId = decodeURIComponent(child);
    const folderLabel = foldersQuery.data?.find((folder) => folder.id === folderId)?.name ?? humanizeSlug(folderId);
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: folderLabel }];
  } else if (section === 'prompts' && resourceId === 'new') {
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: t('lifecycle.newPrompt.untitled') }];
  } else if (section === 'prompts' && resourceId) {
    const editing = child === 'edit' || child === 'revisions';
    const navigationState = state as { promptDraft?: { title?: unknown }; promptTitle?: unknown } | null;
    const promptDraft = navigationState?.promptDraft;
    const promptLabel = promptQuery.data?.title ?? (typeof navigationState?.promptTitle === 'string'
      ? navigationState.promptTitle
      : (child === 'test' || child === 'evaluation') && typeof promptDraft?.title === 'string'
        ? promptDraft.title
        : humanizeSlug(resourceId));
    const folderId = promptQuery.data?.folderId ?? promptQuery.data?.modelName.split('/')[0];
    const folderLabel = foldersQuery.data?.find((folder) => folder.id === folderId)?.name
      ?? (folderId ? humanizeSlug(folderId) : undefined);
    breadcrumbs = [
      { label: sectionTitle, href: '/app/prompts', icon: sectionIcon },
      ...(folderId && folderLabel ? [{ label: folderLabel, href: `/app/prompts/folder/${encodeURIComponent(folderId)}` }] : []),
      { label: promptLabel },
    ];
    if (isPromptDetail) {
      topBarTabs = [
        { value: 'versioning', label: t('lifecycle.overview.tabs.versioning') },
        { value: 'release', label: t('lifecycle.overview.tabs.release') },
        { value: 'logs', label: t('lifecycle.overview.tabs.logs') },
        { value: 'production', label: t('lifecycle.overview.tabs.production') },
        { value: 'evaluation', label: t('lifecycle.overview.tabs.evaluation') },
      ];
      activeTopBarTab = child === 'release' || child === 'logs' || child === 'production' || child === 'evaluation'
        ? child
        : 'versioning';
      onTopBarTabChange = (value) => {
        const suffix = value === 'versioning' ? '' : `/${value}`;
        void navigate(`/app/prompts/${resourceId}${suffix}`);
      };
    } else if (editing) {
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
      tabs={topBarTabs}
      activeTab={activeTopBarTab}
      onTabChange={onTopBarTabChange}
      contextNavigation={tabs}
      mainClassName={isPromptDetail ? 'p-0 sm:p-0 lg:p-0' : undefined}
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
      hideTopBar={isSettings}
    >
      <PromptLifecycleRoutes />
      <FolderFormDialog open={isCreateFolderOpen} onClose={() => setIsCreateFolderOpen(false)} />
    </AppShell>
  );
}
