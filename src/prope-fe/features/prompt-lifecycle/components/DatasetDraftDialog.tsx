import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';

interface DatasetDraftDialogProps {
  open: boolean;
  loading: boolean;
  onClose: () => void;
  onDraft: (brief: string) => void;
}

export function DatasetDraftDialog({ open, loading, onClose, onDraft }: DatasetDraftDialogProps) {
  const { t } = useTranslation();
  const [brief, setBrief] = useState('');

  return (
    <Modal
      open={open}
      title={t('lifecycle.evalDatasets.draftDialog.title')}
      description={t('lifecycle.evalDatasets.draftDialog.description')}
      confirmLabel={t('lifecycle.evalDatasets.draftDialog.confirm')}
      confirmDisabled={brief.trim().length === 0}
      confirmLoading={loading}
      onClose={onClose}
      onConfirm={() => onDraft(brief.trim())}
    >
      <Textarea
        label={t('lifecycle.evalDatasets.draftDialog.brief')}
        placeholder={t('lifecycle.evalDatasets.draftDialog.placeholder')}
        hint={t('lifecycle.evalDatasets.draftDialog.hint')}
        value={brief}
        onChange={(event) => setBrief(event.target.value)}
        className="min-h-32"
      />
    </Modal>
  );
}
