import { ArrowLeft, ArrowRight, ShieldCheck } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';
import { PreservationShell } from '@/features/preservation/components/PreservationShell';
import { OwnerStep } from '@/features/registration/components/OwnerStep';
import { PromptRecordStep } from '@/features/registration/components/PromptRecordStep';
import { RegistrationProgress } from '@/features/registration/components/RegistrationProgress';
import { RegistrationState } from '@/features/registration/components/RegistrationState';
import { RuntimeBindingStep } from '@/features/registration/components/RuntimeBindingStep';
import { useRegisterPromptFlow } from '@/features/registration/useRegisterPromptFlow';

export function RegisterPromptPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const flow = useRegisterPromptFlow();
  const renderStep = () => {
    if (flow.step === 0) return <PromptRecordStep form={flow.form} />;
    if (flow.step === 1 && flow.metadata.data) return <RuntimeBindingStep form={flow.form} metadata={flow.metadata.data} onProviderChange={flow.selectProvider} />;
    if (flow.metadata.data) return <OwnerStep form={flow.form} metadata={flow.metadata.data} onOwnerChange={flow.selectOwner} />;
    return null;
  };

  return (
    <PreservationShell activeId="prompts" title={t('registration.pageTitle')} description={t('registration.pageDescription')} showCreate={false}>
      <div className="mx-auto max-w-copy">
        <button type="button" onClick={() => navigate('/app/prompts')} className="mb-5 inline-flex min-h-10 items-center gap-2 rounded-control px-2 text-body font-semibold text-link focus-visible:outline-2 focus-visible:outline-focus"><ArrowLeft aria-hidden className="size-4" />{t('preservation.actions.back')}</button>
        {flow.metadata.isPending ? <RegistrationState state="loading" /> : null}
        {flow.metadata.isError ? <RegistrationState state="error" onRetry={() => void flow.metadata.refetch()} /> : null}
        {flow.metadata.data && !flow.metadata.data.owners.length ? <RegistrationState state="empty" /> : null}
        {flow.metadata.data?.owners.length ? <form onSubmit={flow.submit} noValidate><RegistrationProgress currentStep={flow.step} /><Card className="mt-6 min-h-0 p-5 sm:p-8"><div className="text-ink">{renderStep()}</div><div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5"><Button type="button" intent="neutral" disabled={flow.step === 0} leadingIcon={<ArrowLeft aria-hidden className="size-4" />} onClick={flow.back}>{t('registration.actions.back')}</Button>{flow.step < 2 ? <Button type="button" trailingIcon={<ArrowRight aria-hidden className="size-4" />} onClick={() => void flow.next()}>{t('registration.actions.continue')}</Button> : <Button type="submit" disabled={!flow.canRegister} loading={flow.registerPrompt.isPending} leadingIcon={<ShieldCheck aria-hidden className="size-4" />}>{t('registration.actions.register')}</Button>}</div>{flow.registerPrompt.isError ? <p role="alert" className="mt-4 rounded-lg bg-danger p-4 text-body text-danger-text">{t('registration.submitError')}</p> : null}</Card></form> : null}
      </div>
    </PreservationShell>
  );
}
