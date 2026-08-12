import { Flask, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';

interface EvaluationStateProps { mode: 'error' | 'empty'; onRetry?: () => void; }

export function EvaluationState({ mode, onRetry }: EvaluationStateProps) {
  const { t } = useTranslation();
  const Icon = mode === 'error' ? WarningCircle : Flask;
  return <section role={mode === 'error' ? 'alert' : undefined} className="grid min-h-72 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel"><div><Icon aria-hidden className="mx-auto size-10 text-muted" /><h2 className="mt-4 text-heading-2 font-semibold">{t(`evaluation.states.${mode}.title`)}</h2><p className="mx-auto mt-2 max-w-copy text-body text-muted">{t(`evaluation.states.${mode}.body`)}</p>{onRetry ? <Button className="mt-5" type="button" intent="neutral" onClick={onRetry}>{t('evaluation.actions.retry')}</Button> : null}</div></section>;
}
