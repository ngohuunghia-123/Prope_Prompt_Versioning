import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

export interface ConvertToXmlDialogProps {
  open: boolean;
  onConvert: () => void;
  onKeepAsIs: () => void;
  onCancel: () => void;
  errorKey?: string;
}

/** Convert the imported source into canonical XML blocks, or store it as it is.
 *
 * Three buttons rather than a yes/no, because escaping a two-button dialog would
 * have to mean one of the two answers, and both of them save a prompt. Cancel
 * goes back to the form having written nothing; the other two both import, and
 * differ only in what the stored body looks like.
 *
 * "Keep as is" now means it. The text is stored inside the nameless `<>` block —
 * unescaped, unstructured, and unwrapped again before dispatch — so the bytes
 * the provider receives are the bytes that were pasted. The copy says where the
 * two markers come from and that they are removed, because a person who reads
 * their own prompt back on the detail screen will see them and should already
 * know they are Prope's rather than something added to their prompt.
 */
export function ConvertToXmlDialog({ open, onConvert, onKeepAsIs, onCancel, errorKey }: ConvertToXmlDialogProps) {
  const { t } = useTranslation();

  return (
    <Modal
      open={open}
      title={t('lifecycle.newPrompt.convert.title')}
      description={t('lifecycle.newPrompt.convert.description')}
      confirmLabel={t('lifecycle.newPrompt.convert.confirm')}
      onClose={onCancel}
      onConfirm={onConvert}
    >
      {errorKey ? <p role="alert" className="mb-3 text-caption text-danger-text">{t(errorKey)}</p> : null}
      <div className="grid gap-3 rounded-xl border border-border bg-subtle p-4">
        <p className="text-caption text-muted">{t('lifecycle.newPrompt.convert.keepHint')}</p>
        <Button type="button" intent="neutral" className="justify-center" onClick={onKeepAsIs}>
          {t('lifecycle.newPrompt.convert.keep')}
        </Button>
      </div>
    </Modal>
  );
}
