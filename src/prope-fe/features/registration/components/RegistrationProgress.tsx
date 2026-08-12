import { Check } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export interface RegistrationProgressProps { currentStep: number; }

export function RegistrationProgress({ currentStep }: RegistrationProgressProps) {
  const { t } = useTranslation();
  const steps = ['record', 'binding', 'owner'] as const;
  return (
    <nav aria-label={t('registration.progress.label')}>
      <ol className="grid grid-cols-3 gap-2">
        {steps.map((step, index) => <li key={step} className="min-w-0">
          <div className={cn('mb-2 h-1 rounded-full bg-border', index <= currentStep && 'bg-secondary')} />
          <div className="flex items-center gap-2"><span aria-hidden className={cn('grid size-6 shrink-0 place-items-center rounded-full border border-border bg-surface text-caption font-semibold text-muted', index < currentStep && 'border-success-strong bg-success text-success-text', index === currentStep && 'border-secondary bg-secondary text-inverse')}>{index < currentStep ? <Check className="size-3.5" weight="bold" /> : index + 1}</span><span className={cn('hidden truncate text-caption text-muted sm:block', index === currentStep && 'font-semibold text-ink')}>{t(`registration.progress.${step}`)}</span></div>
        </li>)}
      </ol>
    </nav>
  );
}
