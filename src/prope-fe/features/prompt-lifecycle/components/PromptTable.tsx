import { Star } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { LifecycleStatus } from '@/features/prompt-lifecycle/components/LifecycleStatus';
import { PromptActionsMenu } from '@/features/prompt-lifecycle/components/PromptActionsMenu';
import { Tag } from '@/components/Tag';
import { useLocaleFormatters } from '@/features/prompt-lifecycle/useLocaleFormatters';
import type { Prompt } from '@/features/prompt-lifecycle/types';
import { MotionTableRow } from '@/components/ui/MotionTableRow';
import { useWorkspaceDisplayNames } from '@/features/prompt-lifecycle/useWorkspaceDisplayNames';
import { promptOverviewPath } from '@/features/prompt-lifecycle/promptUrls';

interface PromptTableProps {
  folderId: string;
  prompts: Prompt[];
}

export function PromptTable({ folderId, prompts }: PromptTableProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { date } = useLocaleFormatters();
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const { userName } = useWorkspaceDisplayNames();

  const toggleFavorite = (promptId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(promptId)) {
        next.delete(promptId);
      } else {
        next.add(promptId);
      }
      return next;
    });
  };

  return (
    <div className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <div className="overflow-x-auto">
        <table className="w-full min-w-3xl border-collapse text-left text-body">
          <thead className="bg-subtle text-caption text-muted">
            <tr>
              <th className="px-4 py-3 font-semibold">{t('lifecycle.folders.detail.table.prompt')}</th>
              <th className="px-4 py-3 font-semibold">{t('lifecycle.folders.detail.table.status')}</th>
              <th className="px-4 py-3 font-semibold">{t('lifecycle.folders.detail.table.owner')}</th>
              <th className="px-4 py-3 font-semibold">{t('lifecycle.folders.detail.table.updated')}</th>
              <th className="px-4 py-3 text-right font-semibold">
                <span className="sr-only">{t('lifecycle.folders.detail.table.action')}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {prompts.map((prompt) => {
              const isFavorite = favorites.has(prompt.id);
              return (
                <MotionTableRow
                  key={prompt.id}
                  onClick={() => void navigate(promptOverviewPath(prompt.modelName), { state: { promptTitle: prompt.title } })}
                  className="cursor-pointer transition-colors duration-(--prope-motion-duration-fast) hover:bg-subtle/60"
                >
                  <td className="px-4 py-4">
                    <strong className="block text-ink">{prompt.title}</strong>
                    <code className="mt-1 block text-caption text-muted">{prompt.modelName}</code>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {prompt.tags.slice(0, 3).map((tag) => (
                        <Tag key={tag} state="neutral">
                          {tag}
                        </Tag>
                      ))}
                      {prompt.tags.length > 3 && (
                        <Tag state="neutral">+{prompt.tags.length - 3}</Tag>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <LifecycleStatus status={prompt.status} />
                  </td>
                  <td className="px-4 py-4 text-muted">{userName(prompt.owner)}</td>
                  <td className="px-4 py-4 text-muted">{date(prompt.updatedAt)}</td>
                  <td className="px-4 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={(e) => toggleFavorite(prompt.id, e)}
                        className="inline-flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-subtle hover:text-warning-text"
                        aria-label={isFavorite ? t('lifecycle.folders.detail.action.unfavorite') : t('lifecycle.folders.detail.action.favorite')}
                      >
                        <Star
                          aria-hidden
                          weight={isFavorite ? 'fill' : 'regular'}
                          className={`size-5 ${isFavorite ? 'text-warning-text' : ''}`}
                        />
                      </button>
                      <PromptActionsMenu folderId={folderId} prompt={prompt} />
                    </div>
                  </td>
                </MotionTableRow>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
