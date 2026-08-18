import { Sparkle } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Radio } from '@/components/ui/Radio';
import type { Revision } from '@/features/prompt-lifecycle/types';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import { cn } from '@/lib/cn';

interface PromptVersionRailProps {
  revisions: Revision[];
  selectedId: string;
  onSelect: (revisionId: string) => void;
  onEditWithAi: () => void;
}

export function PromptVersionRail({ revisions, selectedId, onSelect, onEditWithAi }: PromptVersionRailProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();

  return (
    <aside className="flex min-h-full w-full min-w-0 max-w-full flex-col border-b border-border bg-subtle/50 lg:border-r lg:border-b-0">
      <div className="border-b border-border px-5 py-4">
        <h2 className="!font-sans text-overline font-bold tracking-navigation-overline text-muted uppercase">
          {t('lifecycle.promptDetail.versionTitle')}
        </h2>
      </div>
      <ol className="grid flex-1 content-start gap-2 p-4 sm:grid-cols-2 lg:grid-cols-1">
        <li>
          <Button className="w-full max-w-full min-w-0 justify-start rounded-xl p-3 text-left" intent="primary" leadingIcon={<Sparkle aria-hidden className="size-4 shrink-0" weight="fill" />} onClick={onEditWithAi}>
            <span className="min-w-0 truncate">{t('lifecycle.promptDetail.editWithAi')}</span>
          </Button>
        </li>
        {revisions.map((revision) => {
          const selected = revision.id === selectedId;
          return (
            <li key={revision.id}>
              <Radio
                name="prompt-version"
                checked={selected}
                onChange={() => onSelect(revision.id)}
                label={t('lifecycle.promptDetail.versionValue', { version: revision.number.replace(/^r/, '') })}
                description={format.date(revision.createdAt)}
                className={cn(
                  'w-full max-w-full rounded-xl border p-3 transition-colors duration-(--prope-motion-duration-fast) [&>span:last-child]:min-w-0 [&>span:last-child>span]:truncate',
                  selected ? 'border-secondary bg-surface shadow-inset' : 'border-border bg-canvas hover:bg-surface',
                )}
              />
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
