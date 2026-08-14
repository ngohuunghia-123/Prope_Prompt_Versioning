import { X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useDialogFocus } from '@/components/ui/useDialogFocus';

interface CreateFolderDialogProps {
  open: boolean;
  onClose: () => void;
}

export function CreateFolderDialog({ open, onClose }: CreateFolderDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const containerRef = useDialogFocus(open, onClose);

  const handleSubmit = () => {
    console.log('Creating folder:', { name, description });
    setName('');
    setDescription('');
    onClose();
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-4"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-folder-title"
        className="flex w-full max-w-md flex-col gap-4 rounded-modal bg-surface p-6 text-ink shadow-floating"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id="create-folder-title" className="font-display text-heading-2 font-medium">{t('lifecycle.folders.createTitle')}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"
          >
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <p className="text-body text-muted">{t('lifecycle.folders.createDescription')}</p>
        <div className="mt-2 flex flex-col gap-4">
          <Input
            label={t('lifecycle.folders.folderName')}
            placeholder={t('lifecycle.folders.folderNamePlaceholder')}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            label={t('lifecycle.folders.folderDescription')}
            placeholder={t('lifecycle.folders.folderDescriptionPlaceholder')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-2.5">
          <Button intent="neutral" onClick={onClose}>{t('common.cancel')}</Button>
          <Button intent="primary" onClick={handleSubmit}>{t('lifecycle.folders.createButton')}</Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
