import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

export interface ConvertToXmlDialogProps {
  open: boolean;
  onConvert: () => void;
  onKeepAsIs: () => void;
  onCancel: () => void;
}

/** Convert the imported source into canonical XML blocks, or store it as it is.
 *
 * Three buttons rather than a yes/no, because escaping a two-button dialog would
 * have to mean one of the two answers, and both of them save a prompt. Cancel
 * goes back to the form having written nothing; the other two both import, and
 * differ only in what the stored body looks like.
 *
 * "Keep as is" is not "skip the conversion": a revision body must be canonical
 * XML, so the text is wrapped in a single `<instructions>` block and the
 * original is kept verbatim beside it. The copy says so, because a person who
 * expected their file back byte-for-byte should find that out here rather than
 * on the detail screen.
 */
export function ConvertToXmlDialog({ open, onConvert, onKeepAsIs, onCancel }: ConvertToXmlDialogProps) {
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
      <div className="grid gap-3 rounded-xl border border-border bg-subtle p-4">
        <p className="text-caption text-muted">{t('lifecycle.newPrompt.convert.keepHint')}</p>
        <Button type="button" intent="neutral" className="justify-center" onClick={onKeepAsIs}>
          {t('lifecycle.newPrompt.convert.keep')}
        </Button>
      </div>
    </Modal>
  );
}
