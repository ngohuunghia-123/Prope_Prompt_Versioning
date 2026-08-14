import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Clock } from '@phosphor-icons/react';
import { readRecentPromptsList } from '@/components/promptRecentOpensStorage';
import type { RecentPrompt } from '@/components/promptRecentOpensStorage';

function PromptRecentOpensInner() {
  const { t } = useTranslation();
  const [recent, setRecent] = useState<RecentPrompt[]>([]);

  useEffect(() => {
    setRecent(readRecentPromptsList());
  }, []);

  if (recent.length === 0) {
    return (
      <div className="mt-1 rounded-lg border border-dashed border-border bg-transparent px-3 py-2">
        <p className="text-caption text-muted">{t('navigation.advanced.home.recentPromptsEmpty')}</p>
      </div>
    );
  }

  return (
    <ul className="mt-1 grid gap-1 pl-3">
      {recent.map((prompt) => (
        <li key={prompt.id}>
          <Link
            to={`/app/prompts/${prompt.id}`}
            className="flex min-h-7 min-w-0 items-center gap-1.5 rounded-md px-2 text-caption text-link transition-colors duration-(--prope-motion-duration-fast) hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
          >
            <Clock aria-hidden className="size-3 shrink-0 text-muted" />
            <span className="truncate">{prompt.title}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function PromptRecentOpens() {
  return <PromptRecentOpensInner />;
}
