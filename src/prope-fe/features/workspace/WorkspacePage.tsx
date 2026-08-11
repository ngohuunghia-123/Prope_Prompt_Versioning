import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { WorkspaceAccount } from '@/features/auth/components/WorkspaceAccount';
import { WorkspaceCompactAccount } from '@/features/auth/components/WorkspaceCompactAccount';

export function WorkspacePage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const section = pathname.split('/')[2] ?? 'home';
  const activeId = section === 'prompts' || section === 'vault' || section === 'home' ? 'vault/folder-1' : section === 'evaluation' ? `evaluation/${pathname.split('/')[3] ?? 'datasets'}` : section;
  const sectionKey = ['home', 'prompts', 'reviews', 'notifications', 'providers', 'settings'].includes(section) ? section : 'home';
  return (
    <AppShell activeId={activeId} title={t(`workspace.sections.${sectionKey}.title`)} description={t(`workspace.sections.${sectionKey}.description`)} account={<WorkspaceAccount />} compactAccount={<WorkspaceCompactAccount />}>
      <div aria-hidden className="min-h-[calc(100dvh-9rem)]" />
    </AppShell>
  );
}
