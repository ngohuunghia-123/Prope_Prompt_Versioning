import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowUUpLeft, CheckCircle, Fire, PaperPlaneTilt, RocketLaunch, XCircle } from '@phosphor-icons/react';

import { Notification } from '@/components/Notification';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { latestApproval, releaseStep, type ReviewScreen } from '@/features/prompt-lifecycle/releaseTypes';
import type { useReleaseControl } from '@/features/prompt-lifecycle/useReleaseControl';

interface ReleaseGateProps {
  screen: ReviewScreen;
  control: ReturnType<typeof useReleaseControl>;
  revisionLabel: string;
}

type Prompting =
  | { kind: 'approve' }
  | { kind: 'acknowledge' }
  | { kind: 'reject' }
  | { kind: 'withdraw' }
  | { kind: 'breakGlass' }
  | null;

/**
 * The one act available on this revision, and nothing else.
 *
 * **Three roles, three buttons, never two at once.** Owner submits, Reviewer
 * approves, Admin releases — the seeded permission matrix gives no role two of
 * them (NFR-01), so a screen that offered every button to everybody would be
 * describing a system Prope deliberately is not. What is drawn here is the state
 * of the *revision*; whether this reader may perform it is the server's answer,
 * and a 403 is rendered as an explanation rather than as a failure.
 */
export function ReleaseGate({ screen, control, revisionLabel }: ReleaseGateProps) {
  const { t } = useTranslation();
  const [prompting, setPrompting] = useState<Prompting>(null);
  const [reason, setReason] = useState('');
  const step = releaseStep(screen);
  const decision = latestApproval(screen);

  const close = () => {
    setPrompting(null);
    setReason('');
  };

  const open = (kind: NonNullable<Prompting>['kind']) => {
    control.clearRefusal();
    setReason('');
    setPrompting({ kind });
  };

  // The acknowledgement is asked for only after the server has said it is
  // required, so the common path — evidence present and fresh — stays one click.
  const needsAcknowledgement = control.refusal?.code === 'release_acknowledgement_required';

  const confirm = () => {
    const text = reason.trim();
    switch (prompting?.kind) {
      case 'approve':
        control.approve.mutate({ comment: text || undefined });
        break;
      case 'acknowledge':
        control.approve.mutate({ acknowledgementReason: text });
        break;
      case 'reject':
        control.reject.mutate(text);
        break;
      case 'withdraw':
        control.withdraw.mutate(text);
        break;
      case 'breakGlass':
        control.breakGlass.mutate(text);
        break;
      default:
        return;
    }
    close();
  };

  const tone = step === 'released' ? 'active' : step === 'approved' ? 'pending' : step === 'awaitingApproval' ? 'pending' : 'disabled';

  return (
    <section className="p-4 sm:p-6" aria-labelledby="release-gate-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="release-gate-title" className="font-display text-heading-3 text-ink">
            {t('lifecycle.release.gateTitle', { revision: revisionLabel })}
          </h2>
          <p className="mt-2 max-w-prose text-body text-muted">{t(`lifecycle.release.steps.${step}`)}</p>
        </div>
        <StatusBadge tone={tone}>{t(`lifecycle.release.stepBadge.${step}`)}</StatusBadge>
      </div>

      {screen.self_authored && step === 'awaitingApproval' ? (
        <Notification className="mt-4" tone="info" title={t('lifecycle.release.selfApprovalTitle')}>
          {t('lifecycle.release.selfApprovalDescription')}
        </Notification>
      ) : null}

      {step === 'changesRequested' && decision?.comment ? (
        <Notification className="mt-4" tone="info" title={t('lifecycle.release.changesRequestedTitle')}>
          {decision.comment}
        </Notification>
      ) : null}

      {control.refusal ? (
        <Notification className="mt-4" tone="error" title={t(`lifecycle.release.refusals.${control.refusal.code}`, { defaultValue: t('lifecycle.release.refusals.generic') })} onDismiss={control.clearRefusal}>
          {control.refusal.message}
        </Notification>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-3">
        {step === 'submit' || step === 'changesRequested' ? (
          <Button type="button" loading={control.submit.isPending} disabled={control.working} leadingIcon={<PaperPlaneTilt aria-hidden className="size-4" />} onClick={() => { control.clearRefusal(); control.submit.mutate(); }}>
            {t('lifecycle.release.submit')}
          </Button>
        ) : null}

        {step === 'awaitingApproval' ? (
          <>
            <Button type="button" intent="success" disabled={control.working} leadingIcon={<CheckCircle aria-hidden className="size-4" />} onClick={() => open(needsAcknowledgement ? 'acknowledge' : 'approve')}>
              {t('lifecycle.release.approve')}
            </Button>
            <Button type="button" intent="neutral" disabled={control.working} leadingIcon={<XCircle aria-hidden className="size-4" />} onClick={() => open('reject')}>
              {t('lifecycle.release.requestChanges')}
            </Button>
          </>
        ) : null}

        {step === 'approved' ? (
          <Button type="button" intent="secondary" loading={control.release.isPending} disabled={control.working} leadingIcon={<RocketLaunch aria-hidden className="size-4" />} onClick={() => { control.clearRefusal(); control.release.mutate({}); }}>
            {t('lifecycle.release.publish')}
          </Button>
        ) : null}

        {step === 'released' ? (
          <Button type="button" intent="danger" disabled={control.working} leadingIcon={<ArrowUUpLeft aria-hidden className="size-4" />} onClick={() => open('withdraw')}>
            {t('lifecycle.release.unpublish')}
          </Button>
        ) : null}

        {step === 'unavailable' && screen.released_version_id ? (
          <Button type="button" intent="neutral" loading={control.release.isPending} disabled={control.working} leadingIcon={<RocketLaunch aria-hidden className="size-4" />} onClick={() => { control.clearRefusal(); control.release.mutate({ kind: 'restore' }); }}>
            {t('lifecycle.release.restore')}
          </Button>
        ) : null}
      </div>

      {/* The declared exception, kept visually subordinate: it is available on a
          revision that is not approved, and every use writes a 24-hour follow-up
          task that somebody has to close. */}
      {step === 'awaitingApproval' || step === 'changesRequested' || step === 'submit' ? (
        <details className="mt-5 border-t border-border pt-4">
          <summary className="cursor-pointer text-caption font-semibold text-warning-strong">{t('lifecycle.release.breakGlassSummary')}</summary>
          <p className="mt-2 max-w-prose text-caption text-muted">{t('lifecycle.release.breakGlassDescription')}</p>
          <Button className="mt-3" type="button" intent="warning" size="small" disabled={control.working} leadingIcon={<Fire aria-hidden className="size-4" />} onClick={() => open('breakGlass')}>
            {t('lifecycle.release.breakGlass')}
          </Button>
        </details>
      ) : null}

      <Modal
        open={prompting !== null}
        destructive={prompting?.kind === 'withdraw' || prompting?.kind === 'breakGlass'}
        title={prompting ? t(`lifecycle.release.dialogs.${prompting.kind}.title`) : ''}
        description={prompting ? t(`lifecycle.release.dialogs.${prompting.kind}.description`) : ''}
        confirmLabel={prompting ? t(`lifecycle.release.dialogs.${prompting.kind}.confirm`) : ''}
        // Only `approve` accepts an empty note; every other act here either
        // requires a reason server-side or should not happen without one.
        confirmDisabled={prompting?.kind !== 'approve' && reason.trim().length === 0}
        confirmLoading={control.working}
        onClose={close}
        onConfirm={confirm}
      >
        <Textarea
          className="min-h-28"
          label={prompting ? t(`lifecycle.release.dialogs.${prompting.kind}.label`) : ''}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </Modal>
    </section>
  );
}
