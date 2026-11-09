import { useTranslation } from 'react-i18next';
import { PromptBlockAccordion } from '@/features/prompt-lifecycle/components/PromptBlockAccordion';

export function ChatPromptPreview({ preview }: { preview: Record<string, unknown> }) {
  const { t } = useTranslation();
  if (typeof preview.canonical_xml !== 'string') return null;
  const before = typeof preview.original_source === 'string' ? preview.original_source : '';
  return <section className="min-w-0 space-y-2" aria-label={t('chat.pending.promptPreview')}>
    <h4 className="text-caption font-semibold text-ink">{t('chat.pending.promptPreview')}</h4>
    <PromptBlockAccordion beforeBody={`<>\n${before}\n</>`} body={`<>\n${preview.canonical_xml}\n</>`} sideBySide defaultExpanded />
  </section>;
}
