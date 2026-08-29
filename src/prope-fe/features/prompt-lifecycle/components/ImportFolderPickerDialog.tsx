import { Folder as FolderIcon, FolderPlus } from '@phosphor-icons/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { foldersOptions } from '@/features/prompt-lifecycle/queries';
import { FolderFormDialog } from '@/features/prompt-lifecycle/components/FolderFormDialog';
import { cn } from '@/lib/cn';

interface ImportFolderPickerDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Creating a prompt always happens inside a folder (folder = immutable
 * namespace), so the import entry points ask which folder to target before
 * navigating to that folder's create-prompt page.
 */
export function ImportFolderPickerDialog({ open, onClose }: ImportFolderPickerDialogProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const folders = useQuery({ ...foldersOptions, enabled: open });
  const [selectedId, setSelectedId] = useState<string>();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) {
      setSelectedId(undefined);
      setCreating(false);
    }
  }, [open]);

  const handleConfirm = () => {
    if (!selectedId) return;
    onClose();
    void navigate(`/app/prompts/folder/${encodeURIComponent(selectedId)}/new`);
  };

  return (
    <>
      <Modal
        open={open}
        title={t('lifecycle.importPicker.title')}
        description={t('lifecycle.importPicker.description')}
        confirmLabel={t('lifecycle.importPicker.confirm')}
        confirmDisabled={!selectedId}
        onClose={onClose}
        onConfirm={handleConfirm}
        className="max-w-lg"
      >
        {folders.isPending ? <p className="text-body text-muted">{t('lifecycle.importPicker.loading')}</p> : null}
        {folders.isError ? <p role="alert" className="text-body text-danger-text">{t('lifecycle.folders.error.unknown')}</p> : null}
        {folders.data && folders.data.length === 0 ? (
          <p className="text-body text-muted">{t('lifecycle.importPicker.empty')}</p>
        ) : null}
        {folders.data && folders.data.length > 0 ? (
          <div role="listbox" aria-label={t('lifecycle.importPicker.title')} className="flex max-h-64 flex-col gap-2 overflow-y-auto pr-1">
            {folders.data.map((folder) => {
              const selected = folder.id === selectedId;
              return (
                <button
                  key={folder.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => setSelectedId(folder.id)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-focus',
                    selected ? 'border-secondary bg-accent-soft' : 'border-border bg-canvas hover:border-secondary hover:bg-subtle',
                  )}
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg text-white" style={{ backgroundColor: folder.color }}>
                    <FolderIcon aria-hidden className="size-4" weight="duotone" />
                  </span>
                  <span className="min-w-0">
                    <strong className="block truncate text-body font-semibold text-ink">{folder.name}</strong>
                    <span className="block truncate text-caption text-muted">{folder.description}</span>
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}
        <Button
          type="button"
          intent="neutral"
          size="small"
          leadingIcon={<FolderPlus aria-hidden className="size-4" />}
          className="w-fit"
          onClick={() => setCreating(true)}
        >
          {t('lifecycle.importPicker.createFolder')}
        </Button>
      </Modal>
      <FolderFormDialog open={creating} onClose={() => setCreating(false)} onSaved={(folder) => setSelectedId(folder.id)} />
    </>
  );
}
