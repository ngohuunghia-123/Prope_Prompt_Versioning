import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import type { BreadcrumbItem } from '@/components/TopBar';
import type { TabItem } from '@/components/Tabs';
import { WorkspaceAccount } from '@/features/auth/components/WorkspaceAccount';
import { WorkspaceCompactAccount } from '@/features/auth/components/WorkspaceCompactAccount';
import { PromptLifecycleRoutes } from '@/features/prompt-lifecycle/PromptLifecycleRoutes';
import { useLifecycleNavigation } from '@/features/prompt-lifecycle/useLifecycleNavigation';

function humanizeSlug(value: string) {
  return value.split('-').map((part) => part ? `${part[0]?.toUpperCase()}${part.slice(1)}` : '').join(' ');
}

export function WorkspacePage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const items = useLifecycleNavigation();
  const segments = pathname.split('/').filter(Boolean).slice(1);
  const [section = 'prompts', resourceId, child, childId] = segments;
  const activeId = section === 'reviews' ? 'vault/reviews' : section === 'providers' ? 'vault/providers' : section === 'calls' ? 'vault/calls' : 'vault/prompts';
  const sectionKey = ['prompts', 'reviews', 'providers', 'calls'].includes(section) ? section : 'prompts';
  const sectionTitle = t(`workspace.sections.${sectionKey}.title`);
  const sectionIcon = section === 'reviews' ? <ClockCounterClockwise className="size-4" /> : section === 'providers' ? <PlugsConnected className="size-4" /> : section === 'calls' ? <Scroll className="size-4" /> : <FolderOpen className="size-4" />;
  let breadcrumbs: BreadcrumbItem[] = [{ label: sectionTitle, icon: sectionIcon }];
  let tabs: TabItem[] | undefined;
  let activeTab: string | undefined;
  let onTabChange: ((value: string) => void) | undefined;

  if (section === 'prompts' && resourceId === 'new') {
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: t('lifecycle.editor.registerTitle') }];
    tabs = [{ value: 'overview', label: t('lifecycle.editor.overviewTab') }, { value: 'editor', label: t('lifecycle.editor.editorTab') }];
    activeTab = 'editor';
    onTabChange = (value) => { if (value === 'overview') void navigate('/app/prompts'); };
  } else if (section === 'prompts' && resourceId) {
    const promptLabel = humanizeSlug(resourceId);
    const editing = child === 'revisions' && childId === 'new';
    breadcrumbs = [{ label: sectionTitle, href: '/app/prompts', icon: sectionIcon }, { label: promptLabel, href: editing ? `/app/prompts/${resourceId}` : undefined }, ...(editing ? [{ label: t('lifecycle.editor.editTitle') }] : [])];
    tabs = [{ value: 'overview', label: t('lifecycle.editor.overviewTab') }, { value: 'editor', label: t('lifecycle.editor.editorTab') }];
    activeTab = editing ? 'editor' : 'overview';
    onTabChange = (value) => void navigate(value === 'editor' ? `/app/prompts/${resourceId}/revisions/new` : `/app/prompts/${resourceId}`);
  } else if (section === 'reviews' && resourceId) {
    breadcrumbs = [{ label: sectionTitle, href: '/app/reviews', icon: sectionIcon }, { label: humanizeSlug(resourceId) }];
  } else if (section === 'releases' && resourceId) {
    breadcrumbs = [{ label: t('workspace.sections.prompts.title'), href: '/app/prompts', icon: <FolderOpen className="size-4" /> }, { label: t('lifecycle.release.title') }, { label: resourceId }];
  }

  return <AppShell items={items} activeId={activeId} breadcrumbs={breadcrumbs} tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} account={<WorkspaceAccount />} compactAccount={<WorkspaceCompactAccount />}><PromptLifecycleRoutes /></AppShell>;
}
import { ClockCounterClockwise, FolderOpen, PlugsConnected, Scroll } from '@phosphor-icons/react';
