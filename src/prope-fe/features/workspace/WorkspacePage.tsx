import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { WorkspaceAccount } from '@/features/auth/components/WorkspaceAccount';
import { WorkspaceCompactAccount } from '@/features/auth/components/WorkspaceCompactAccount';
import { PromptLifecycleRoutes } from '@/features/prompt-lifecycle/PromptLifecycleRoutes';
import { useLifecycleNavigation } from '@/features/prompt-lifecycle/useLifecycleNavigation';

export function WorkspacePage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const items = useLifecycleNavigation();
  const section = pathname.split('/')[2] ?? 'prompts';
  const activeId = section === 'reviews' ? 'vault/reviews' : section === 'providers' ? 'vault/providers' : section === 'calls' ? 'vault/calls' : 'vault/prompts';
  const sectionKey = ['prompts', 'reviews', 'providers', 'calls'].includes(section) ? section : 'prompts';
  return (
    <AppShell items={items} activeId={activeId} title={t(`workspace.sections.${sectionKey}.title`)} description={t(`workspace.sections.${sectionKey}.description`)} account={<WorkspaceAccount />} compactAccount={<WorkspaceCompactAccount />}>
      <PromptLifecycleRoutes />
    </AppShell>
  );
}
