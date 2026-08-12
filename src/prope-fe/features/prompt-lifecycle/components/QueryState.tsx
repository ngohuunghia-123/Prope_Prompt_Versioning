import { WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';

export interface QueryStateProps {
  state: 'loading' | 'error' | 'empty';
  onRetry?: () => void;
}

export function QueryState({ state, onRetry }: QueryStateProps) {
  const { t } = useTranslation();
  if (state === 'loading') {
    return (
      <div role="status" className="grid min-h-64 place-items-center rounded-modal border border-border bg-surface p-8 text-body text-muted shadow-panel">
        {t('common.loading')}
      </div>
    );
  }
  return (
    <div className="grid min-h-64 place-items-center rounded-modal border border-border bg-surface p-8 text-center shadow-panel">
      <div className="grid max-w-md gap-3 justify-items-center">
        <WarningCircle aria-hidden className="size-8 text-secondary" />
        <h2 className="font-display text-heading-3 text-ink">{t(`lifecycle.states.${state}.title`)}</h2>
        <p className="text-body text-muted">{t(`lifecycle.states.${state}.description`)}</p>
        {state === 'error' && onRetry ? <Button type="button" intent="neutral" onClick={onRetry}>{t('common.tryAgain')}</Button> : null}
      </div>
    </div>
  );
}
