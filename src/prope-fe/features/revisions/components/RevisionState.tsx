import { ClockCounterClockwise, LockKey, WarningCircle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';

interface RevisionStateProps {
  mode: 'empty' | 'denied' | 'error';
  promptId: string;
  onRetry?: () => void;
}

export function RevisionState({ mode, promptId, onRetry }: RevisionStateProps) {
  const { t } = useTranslation();
  const Icon = mode === 'denied' ? LockKey : mode === 'empty' ? ClockCounterClockwise : WarningCircle;
  return (
    <section role={mode === 'error' ? 'alert' : 'status'} className="grid min-h-80 place-items-center rounded-panel border border-border bg-surface p-6 text-center shadow-panel">
      <div className="max-w-copy">
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-subtle text-secondary"><Icon aria-hidden className="size-6" /></span>
        <h1 className="mt-4 text-heading-2 font-semibold">{t(`revisions.states.${mode}.title`)}</h1>
        <p className="mt-2 text-body text-muted">{t(`revisions.states.${mode}.body`)}</p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {mode === 'error' && onRetry ? <Button onClick={onRetry}>{t('revisions.actions.retry')}</Button> : null}
          {mode === 'empty' ? <Link to={`/app/prompts/${promptId}/revisions/new`} className="inline-flex min-h-10 items-center rounded-xl bg-primary px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus">{t('revisions.actions.createFirst')}</Link> : null}
          <Link to={`/app/prompts/${promptId}`} className="inline-flex min-h-10 items-center rounded-xl border border-border bg-surface px-4 text-body font-semibold uppercase tracking-button text-ink shadow-raised focus-visible:outline-2 focus-visible:outline-focus">{t('revisions.actions.returnToPrompt')}</Link>
        </div>
      </div>
    </section>
  );
}
