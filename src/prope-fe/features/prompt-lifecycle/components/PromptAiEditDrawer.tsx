import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Textarea } from '@/components/ui/Textarea';

interface PromptAiEditDrawerProps {
  open: boolean;
  value: string;
  loading: boolean;
  error: boolean;
  onChange: (value: string) => void;
  onClose: () => void;
  onApply: () => void;
}

export function PromptAiEditDrawer({ open, value, loading, error, onChange, onClose, onApply }: PromptAiEditDrawerProps) {
  const { t } = useTranslation();

  return (
    <Drawer open={open} onClose={onClose} side="right" title={t('lifecycle.promptDetail.aiDrawerTitle')}>
      <div className="flex h-full flex-col p-5">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <Textarea
            label={t('lifecycle.promptDetail.aiEditedVersion')}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={loading}
            error={error ? t('lifecycle.promptDetail.aiEditError') : undefined}
            className="min-h-96 resize-none"
          />
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4">
          <Button type="button" intent="neutral" onClick={onClose}>{t('common.cancel')}</Button>
          <Button type="button" onClick={onApply} disabled={loading || error || !value.trim()} loading={loading}>{t('lifecycle.promptDetail.apply')}</Button>
        </div>
      </div>
    </Drawer>
  );
}
