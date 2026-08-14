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
  showEditAction?: boolean;
}

export function PromptVersionRail({ revisions, selectedId, onSelect, onEditWithAi, showEditAction = true }: PromptVersionRailProps) {
  const { t } = useTranslation();
  const format = useLocaleFormatters();

  return (
    <aside className="flex min-h-full flex-col border-b border-border bg-subtle/50 lg:col-span-1 lg:border-r lg:border-b-0">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-overline font-bold tracking-navigation-overline text-muted uppercase">
          {t('lifecycle.promptDetail.versionTitle')}
        </h2>
      </div>
      {showEditAction ? (
        <div className="border-b border-border p-4">
          <Button className="w-full" intent="neutral" leadingIcon={<Sparkle aria-hidden className="size-4" weight="fill" />} onClick={onEditWithAi}>
            {t('lifecycle.promptDetail.editWithAi')}
          </Button>
        </div>
      ) : null}
      <ol className="grid flex-1 content-start gap-2 p-4">
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
                  'w-full rounded-xl border p-3 transition-colors duration-(--prope-motion-duration-fast)',
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
