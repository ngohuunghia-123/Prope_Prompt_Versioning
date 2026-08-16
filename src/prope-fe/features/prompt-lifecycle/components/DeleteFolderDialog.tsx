import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import type { Folder } from '@/features/prompt-lifecycle/folderTypes';
import { useDeleteFolderMutation } from '@/features/prompt-lifecycle/queries';

interface DeleteFolderDialogProps {
  folder: Folder | undefined;
  onClose: () => void;
  onDeleted?: () => void;
}

/**
 * Confirm removing a folder's label.
 *
 * **The copy says the prompts are untouched because they genuinely are.** There
 * is no foreign key from `prompt_property` to `registry.folder`: deleting the
 * row drops the name, the description and the colour, and the namespace reverts
 * to a derived card. The server still refuses a non-empty folder — a delete that
 * reads destructive should not be one people learn to click through — so this
 * dialog never opens on one, and the guard below is the second line rather than
 * the first.
 */
export function DeleteFolderDialog({ folder, onClose, onDeleted }: DeleteFolderDialogProps) {
  const { t } = useTranslation();
  const mutation = useDeleteFolderMutation();
  const blocked = (folder?.promptCount ?? 0) > 0;

  return (
    <Modal
      open={folder !== undefined}
      destructive
      title={t('lifecycle.folders.deleteTitle')}
      description={blocked
        ? t('lifecycle.folders.deleteBlocked', { count: folder?.promptCount ?? 0 })
        : t('lifecycle.folders.deleteDescription', { name: folder?.name ?? '' })}
      confirmLabel={t('lifecycle.folders.delete')}
      confirmDisabled={blocked}
      confirmLoading={mutation.isPending}
      onClose={onClose}
      onConfirm={() => {
        if (!folder || blocked) return;
        mutation.mutate(folder.id, {
          onSuccess: () => {
            onDeleted?.();
            onClose();
          },
        });
      }}
    >
      {mutation.isError ? (
        <p role="alert" className="text-caption text-danger-text">
          {t('lifecycle.folders.error.unknown')}
        </p>
      ) : null}
    </Modal>
  );
}
