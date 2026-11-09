import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SegmentedControl } from '@/components/SegmentedControl';
import { DirectCaptureForm } from '@/features/connectors/DirectCaptureForm';
import { OpenRevisionForm } from '@/features/connectors/OpenRevisionForm';
import { RevisionWorkspace } from '@/features/connectors/RevisionWorkspace';

export function DirectWorkspace() {
  const { t } = useTranslation(); const [mode, setMode] = useState('paste');
  const [selected, setSelected] = useState<{ prompt_id: string; version_id: string }>();
  return <section className="space-y-4">
    <SegmentedControl label={t('connector.startMode')} name="connector-start" value={mode} onValueChange={setMode}
      options={[{ value: 'paste', label: t('connector.directTitle') }, { value: 'open', label: t('connector.openExisting') }]} />
    {mode === 'paste' ? <DirectCaptureForm /> : <OpenRevisionForm onOpen={setSelected} />}
    {mode === 'open' && selected ? <RevisionWorkspace key={`${selected.prompt_id}:${selected.version_id}`} promptId={selected.prompt_id} versionId={selected.version_id} /> : null}
  </section>;
}
