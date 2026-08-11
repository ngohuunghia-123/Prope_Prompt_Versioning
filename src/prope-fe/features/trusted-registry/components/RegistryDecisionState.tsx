import { ArrowLeft, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { buttonVariants } from '@/components/ui/buttonVariants';
import type { RegistryPrompt } from '@/features/trusted-registry/types';

export interface RegistryDecisionStateProps { prompt: RegistryPrompt; mode: 'untrusted'; }

export function RegistryDecisionState({ prompt, mode }: RegistryDecisionStateProps) {
  const { t } = useTranslation();
  return (
    <section className="grid min-h-96 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel">
      <div className="max-w-copy">
        <span aria-hidden className="mx-auto grid size-16 place-items-center rounded-full bg-subtle text-muted"><WarningCircle className="size-7" /></span>
        <StatusBadge tone="pending" className="mx-auto mt-5">{t(`trustedRegistry.status.${prompt.status}`)}</StatusBadge>
        <h1 className="mt-5 text-heading-2 font-semibold">{t(`trustedRegistry.decision.${mode}.title`)}</h1>
        <p className="mx-auto mt-3 max-w-auth text-body-large text-muted">{t(`trustedRegistry.decision.${mode}.body`, { name: prompt.title, revision: prompt.currentRevision })}</p>
        <Link to="/app/registry" className={`${buttonVariants({ intent: 'neutral' })} mt-6`}><ArrowLeft aria-hidden className="size-4" />{t('trustedRegistry.actions.backToResults')}</Link>
      </div>
    </section>
  );
}
