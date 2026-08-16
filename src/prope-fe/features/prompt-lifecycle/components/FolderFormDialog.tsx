import { Check, X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import { FOLDER_COLORS, folderColor, type Folder } from '@/features/prompt-lifecycle/folderTypes';
import { useCreateFolderMutation, useUpdateFolderMutation } from '@/features/prompt-lifecycle/queries';
import { ApiError } from '@/lib/apiClient';
import { isValidSlug, slugify } from '@/lib/slugify';

interface FolderFormDialogProps {
  open: boolean;
  /** Absent means create. Present means edit — including a folder with no row yet. */
  folder?: Folder;
  onClose: () => void;
  onSaved?: (folder: Folder) => void;
}

/**
 * The refusal codes this dialog can meet, mapped onto catalogue keys.
 *
 * ADR-0053 rule: the client renders the machine `code` and never the `message`.
 * A code with no entry here falls through to `unknown` rather than rendering as
 * nothing at all, which is the silent failure the closed `ErrorCode` set exists
 * to make impossible on the server side.
 */
const KNOWN_CODES = new Set(['registry_folder_slug_taken', 'registry_folder_not_empty']);

function errorKey(error: unknown): string {
  if (error instanceof ApiError && KNOWN_CODES.has(error.code)) {
    return `lifecycle.folders.error.${error.code}`;
  }
  // `requireRealRegistry` throws a plain Error, not an ApiError.
  if (error instanceof Error && error.message.includes('real API')) {
    return 'lifecycle.folders.error.mockMode';
  }
  return 'lifecycle.folders.error.unknown';
}

/**
 * Create a folder, or name an existing one.
 *
 * The two modes are one component because they are one form: the only field
 * that differs is `slug`, which is editable while creating and frozen
 * afterwards. A-021 makes `namespace/name` the address a consuming product
 * calls, so moving the first half would break every caller with no error
 * anywhere — the field stays visible in edit mode, disabled and explained,
 * rather than disappearing, because a slug the author cannot see is one they
 * will assume the rename changed.
 */
export function FolderFormDialog({ open, folder, onClose, onSaved }: FolderFormDialogProps) {
  const { t } = useTranslation();
  const containerRef = useDialogFocus(open, onClose);
  const editing = folder !== undefined;

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  // Once the author edits the slug by hand, the name stops driving it. Without
  // this, typing the rest of a Vietnamese name would silently overwrite the
  // `support` they deliberately typed.
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState('');
  const [color, setColor] = useState<string>(FOLDER_COLORS[0]);

  const createMutation = useCreateFolderMutation();
  const updateMutation = useUpdateFolderMutation();
  const mutation = editing ? updateMutation : createMutation;

  // Reset on every open, not on mount: the dialog stays mounted between edits,
  // so a second folder opened after a first would otherwise show the first one's
  // values for a frame.
  useEffect(() => {
    if (!open) return;
    setName(folder?.name ?? '');
    setSlug(folder?.id ?? '');
    setSlugTouched(false);
    // An undeclared folder's description is the `slug/*` model-name pattern the
    // server generated, which is not prose anybody wrote — starting the field
    // empty is more honest than asking them to delete it.
    setDescription(folder?.declared ? folder.description : '');
    setColor(folder?.color ?? FOLDER_COLORS[0]);
    createMutation.reset();
    updateMutation.reset();
    // Mutation objects are new every render; depending on them would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, folder]);

  if (!open) return null;

  const effectiveSlug = editing ? slug : slugTouched ? slug : slugify(name);
  const slugOk = isValidSlug(effectiveSlug);
  const nameOk = name.trim().length > 0;
  const canSubmit = nameOk && (editing || slugOk) && !mutation.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const done = (saved: Folder) => {
      onSaved?.(saved);
      onClose();
    };

    if (editing) {
      updateMutation.mutate(
        { slug: folder.id, name: name.trim(), description, color },
        { onSuccess: done },
      );
      return;
    }

    createMutation.mutate(
      { slug: effectiveSlug, name: name.trim(), description, color },
      { onSuccess: done },
    );
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-4"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="folder-form-title"
        className="flex max-h-[90vh] w-full max-w-md flex-col gap-4 overflow-y-auto rounded-modal bg-surface p-6 text-ink shadow-floating"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 id="folder-form-title" className="font-display text-heading-2 font-medium">
            {t(editing ? 'lifecycle.folders.editTitle' : 'lifecycle.folders.createTitle')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="grid size-10 place-items-center rounded-full text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"
          >
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <p className="text-body text-muted">
          {t(editing ? 'lifecycle.folders.editDescription' : 'lifecycle.folders.createDescription')}
        </p>

        <div className="flex flex-col gap-4">
          <Input
            label={t('lifecycle.folders.folderName')}
            placeholder={t('lifecycle.folders.folderNamePlaceholder')}
            value={name}
            autoFocus
            onChange={(event) => {
              setName(event.target.value);
              // Keep the colour tracking the slug until somebody picks one, so
              // the swatch matches what a derived card would have shown.
              if (!editing && !slugTouched) setColor(folderColor(slugify(event.target.value)));
            }}
          />

          <Input
            label={t('lifecycle.folders.slug')}
            placeholder={t('lifecycle.folders.slugPlaceholder')}
            value={effectiveSlug}
            disabled={editing}
            onChange={(event) => {
              setSlugTouched(true);
              setSlug(event.target.value);
              setColor(folderColor(event.target.value));
            }}
            error={!editing && effectiveSlug !== '' && !slugOk ? t('lifecycle.folders.slugInvalid') : undefined}
            hint={editing
              ? t('lifecycle.folders.slugLocked')
              : t('lifecycle.folders.slugHint', { slug: effectiveSlug || t('lifecycle.folders.slugPlaceholder') })}
          />

          <Textarea
            label={t('lifecycle.folders.folderDescription')}
            placeholder={t('lifecycle.folders.folderDescriptionPlaceholder')}
            value={description}
            rows={3}
            className="min-h-24"
            onChange={(event) => setDescription(event.target.value)}
          />

          <fieldset className="flex flex-col gap-2">
            <legend className="text-body font-medium text-ink">{t('lifecycle.folders.color')}</legend>
            <div className="flex flex-wrap gap-2">
              {FOLDER_COLORS.map((swatch, index) => (
                <button
                  key={swatch}
                  type="button"
                  aria-label={t('lifecycle.folders.colorOption', { index: index + 1 })}
                  aria-pressed={color === swatch}
                  onClick={() => setColor(swatch)}
                  className="grid size-9 place-items-center rounded-full text-white outline-offset-2 transition-transform duration-(--prope-motion-duration-fast) hover:scale-110 focus-visible:outline-2 focus-visible:outline-focus aria-pressed:outline-2 aria-pressed:outline-ink"
                  style={{ backgroundColor: swatch }}
                >
                  {color === swatch ? <Check aria-hidden className="size-4" weight="bold" /> : null}
                </button>
              ))}
            </div>
          </fieldset>
        </div>

        {mutation.isError ? (
          <p role="alert" className="text-caption text-danger-text">{t(errorKey(mutation.error))}</p>
        ) : null}

        <div className="mt-2 flex flex-wrap gap-2.5">
          <Button intent="neutral" onClick={onClose}>{t('common.cancel')}</Button>
          <Button
            intent="primary"
            onClick={handleSubmit}
            disabled={!canSubmit}
            loading={mutation.isPending}
          >
            {t(editing ? 'lifecycle.folders.saveButton' : 'lifecycle.folders.createButton')}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
