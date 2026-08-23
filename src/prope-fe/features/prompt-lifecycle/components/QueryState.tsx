import { WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { ContentSkeleton, type ContentSkeletonLayout } from '@/components/ui/ContentSkeleton';

export interface QueryStateProps {
  state: 'loading' | 'error' | 'empty';
  onRetry?: () => void;
  titleOverride?: string;
  descriptionOverride?: string;
  loadingLayout?: ContentSkeletonLayout;
}

export function QueryState({ state, onRetry, titleOverride, descriptionOverride, loadingLayout = 'page' }: QueryStateProps) {
  const { t } = useTranslation();
  if (state === 'loading') {
    return <ContentSkeleton label={t('common.loading')} layout={loadingLayout} />;
  }
  return (
    <div className="grid min-h-64 place-items-center rounded-modal border border-border bg-surface p-8 text-center shadow-panel">
      <div className="grid max-w-md gap-3 justify-items-center">
        <WarningCircle aria-hidden className="size-8 text-secondary" />
        <h2 className="font-display text-heading-3 text-ink">{titleOverride ?? t(`lifecycle.states.${state}.title`)}</h2>
        <p className="text-body text-muted">{descriptionOverride ?? t(`lifecycle.states.${state}.description`)}</p>
        {state === 'error' && onRetry ? <Button type="button" intent="neutral" onClick={onRetry}>{t('common.tryAgain')}</Button> : null}
      </div>
    </div>
  );
}
