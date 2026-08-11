import { ArrowLeft, WarningCircle } from '@phosphor-icons/react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { registryDetailOptions } from '@/features/trusted-registry/api';
import { RegistryDecisionState } from '@/features/trusted-registry/components/RegistryDecisionState';
import { TrustedRevisionPanel } from '@/features/trusted-registry/components/TrustedRevisionPanel';

export function TrustedPromptDetailPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const prompt = useQuery(registryDetailOptions(id));
  return (
    <PreservationShell activeId="registry" title={t('trustedRegistry.detail.pageTitle')} description={t('trustedRegistry.detail.pageDescription')}>
      <div className="mx-auto max-w-content space-y-5">
        <Link to="/app/registry" className="inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('trustedRegistry.actions.backToResults')}</Link>
        {prompt.isPending ? <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} /> : null}
        {prompt.isError ? <section role="alert" className="grid min-h-80 place-items-center rounded-panel border border-danger-strong bg-danger p-6 text-center"><div><WarningCircle aria-hidden className="mx-auto size-9 text-danger-text" /><h1 className="mt-4 text-heading-2 font-semibold">{t('trustedRegistry.error.notFoundTitle')}</h1><p className="mt-2 text-body text-danger-text">{t('trustedRegistry.error.notFoundBody')}</p></div></section> : null}
        {prompt.data?.revisionTrust === 'untrusted' ? <RegistryDecisionState prompt={prompt.data} mode="untrusted" /> : null}
        {prompt.data?.revisionTrust === 'trusted' ? <TrustedRevisionPanel prompt={prompt.data} /> : null}
      </div>
    </PreservationShell>
  );
}
