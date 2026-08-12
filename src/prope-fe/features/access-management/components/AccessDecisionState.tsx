import { LockKeyOpen, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';

interface AccessDecisionStateProps { promptId: string; mode: 'denied' | 'empty' | 'error'; onRetry?: () => void; }

export function AccessDecisionState({ promptId, mode, onRetry }: AccessDecisionStateProps) {
  const { t } = useTranslation();
  const Icon = mode === 'denied' ? LockKeyOpen : WarningCircle;
  return (
    <section role={mode === 'error' ? 'alert' : undefined} className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel">
      <div className="max-w-copy"><Icon aria-hidden className="mx-auto size-10 text-secondary" /><h1 className="mt-4 text-heading-2 font-semibold">{t(`accessManagement.states.${mode}.title`)}</h1><p className="mt-2 text-body text-muted">{t(`accessManagement.states.${mode}.body`)}</p><div className="mt-5 flex justify-center gap-2">{mode === 'error' && onRetry ? <Button onClick={onRetry}>{t('preservation.actions.retry')}</Button> : null}<Link to={`/app/prompts/${promptId}`} className="inline-flex min-h-10 items-center rounded-xl border border-border bg-surface px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus">{t('accessManagement.actions.returnToPrompt')}</Link></div></div>
    </section>
  );
}
