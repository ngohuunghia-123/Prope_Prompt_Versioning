import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { callHost } from '@/features/connectors/bridge';
import { directRevisionSchema } from '@/features/connectors/directContracts';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import type { RevisionRead } from '@/features/prompt-lifecycle/types';

export function RevisionEditor({ revision }: { revision: RevisionRead }) {
  const { t } = useTranslation();
  const form = useForm<z.infer<typeof directRevisionSchema>>({ resolver: zodResolver(directRevisionSchema), defaultValues: { prompt_id: revision.prompt_id, version_id: revision.version_id, format: 'xml', source: revision.body } });
  const stage = useMutation({ mutationFn: (value: z.infer<typeof directRevisionSchema>) => callHost('stage_revision', value) });
  return <form className="space-y-3" onSubmit={form.handleSubmit((value) => stage.mutate(value))}>
    <p className="text-caption text-muted">{t('connector.editRevisionHint')}</p>
    <Textarea label={t('connector.original')} readOnly value={revision.original_body} />
    <Textarea label={t('connector.canonicalEditor')} rows={12} {...form.register('source')} error={form.formState.errors.source ? t('connector.invalid') : undefined} />
    <ConnectorError error={stage.error} />
    <Button type="submit" loading={stage.isPending} disabled={stage.isSuccess}>{t('connector.reviewEdit')}</Button>
    {stage.isSuccess ? <p role="status">{t('connector.proposalReady')}</p> : null}
  </form>;
}
