import { Controller } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Select } from '@/components/ui/Select';
import { Checkbox } from '@/components/ui/Checkbox';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';
import { ConnectorError } from '@/features/connectors/ConnectorError';
import { useRevisionContentComparison } from '@/features/connectors/useRevisionContentComparison';

export function RevisionContentComparison({ promptId, versionId }: { promptId: string; versionId: string }) {
  const { t } = useTranslation(); const diff = useRevisionContentComparison(promptId, versionId);
  const options = (diff.revisions.data ?? []).map((revision) => ({ value: revision.version_id, label: t('connector.revision', { number: revision.revision_number }) }));
  return <section className="space-y-3">
    <h3 className="font-display text-heading-3">{t('connector.contentComparisonTitle')}</h3>
    <p className="text-body text-muted">{t('connector.contentComparisonHint')}</p>
    <ConnectorError error={diff.revisions.error ?? diff.before.error ?? diff.after.error} />
    {diff.loading ? <p role="status">{t('common.loading')}</p> : null}
    {diff.revisions.isSuccess && options.length < 2 ? <p role="status">{t('connector.needTwoRevisions')}</p> : null}
    {options.length >= 2 ? <>
      <div className="grid gap-3 sm:grid-cols-2">
        {(['before_version_id', 'after_version_id'] as const).map((name) => <Controller key={name} control={diff.form.control} name={name} render={({ field }) => <Select
          label={t(name === 'before_version_id' ? 'connector.beforeRevision' : 'connector.afterRevision')} value={field.value} onValueChange={field.onChange}
          options={[{ value: '', label: t('connector.choose') }, ...options.map((option) => ({ ...option, disabled: option.value === (name === 'before_version_id' ? diff.afterId : diff.beforeId) }))]} />} />)}
      </div>
      <Controller control={diff.form.control} name="body_kind" render={({ field }) => <Select label={t('connector.comparedContent')} value={field.value} onValueChange={field.onChange}
        options={[{ value: 'canonical', label: t('connector.canonicalEditor') }, { value: 'original', label: t('connector.original') }]} />} />
      <Controller control={diff.form.control} name="only_changed" render={({ field }) => <Checkbox label={t('connector.onlyContentChanges')} checked={field.value} onChange={field.onChange} />} />
    </> : null}
    {diff.invalidTarget ? <p role="alert" className="text-danger-text">{t('connector.invalid')}</p> : null}
    {diff.ready && diff.beforeBody !== undefined && diff.afterBody !== undefined ? <>
      <p className="break-all text-caption text-muted">{t('connector.contentComparisonDirection', { before: diff.beforeId, after: diff.afterId })}</p>
      {diff.beforeBody === diff.afterBody ? <p role="status">{t('connector.identicalContent')}</p>
        // Keep XML markup and block order in the diff as literal source text.
        : <PromptBlockAccordion key={`${diff.beforeId}:${diff.afterId}:${diff.bodyKind}`} beforeBody={`<>\n${diff.beforeBody}\n</>`} body={`<>\n${diff.afterBody}\n</>`} sideBySide onlyChanged={diff.onlyChanged} />}
    </> : null}
  </section>;
}
