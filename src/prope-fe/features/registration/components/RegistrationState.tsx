import { ArrowClockwise, Users } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';

export interface RegistrationStateProps { state: 'loading' | 'error' | 'empty'; onRetry?: () => void; }

export function RegistrationState({ state, onRetry }: RegistrationStateProps) {
  const { t } = useTranslation();
  if (state === 'loading') return <div className="h-96 animate-pulse rounded-panel bg-subtle motion-reduce:animate-none" aria-label={t('common.loading')} />;
  return <section role={state === 'error' ? 'alert' : 'status'} className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel"><div><Users aria-hidden className="mx-auto size-10 text-muted" /><h2 className="mt-4 text-heading-2 font-semibold">{t(`registration.states.${state}.title`)}</h2><p className="mt-2 text-body text-muted">{t(`registration.states.${state}.body`)}</p>{state === 'error' && onRetry ? <Button type="button" intent="neutral" className="mt-5" leadingIcon={<ArrowClockwise aria-hidden className="size-4" />} onClick={onRetry}>{t('registration.actions.retry')}</Button> : null}</div></section>;
}
