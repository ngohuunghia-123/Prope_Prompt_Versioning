import type { ReactNode } from 'react';
import { NavigationBrandHeader } from '@/components/NavigationBrandHeader';
import { NavigationChatPanel } from '@/components/NavigationChatPanel';
import { NavigationHomePanel } from '@/components/NavigationHomePanel';
import { NavigationModeTabs } from '@/components/NavigationModeTabs';
import { NavigationSearchPanel } from '@/components/NavigationSearchPanel';
import { NavigationUpdatesPanel } from '@/components/NavigationUpdatesPanel';
import type { NavigationItem } from '@/components/NavigationMenu';
import type { NavigationMode } from '@/components/navigationTypes';
import { useChat } from '@/features/chat/ChatContext';

export interface NavigationExpandedProps {
  activeId: string;
  items?: NavigationItem[];
  account?: ReactNode;
  mode: NavigationMode;
  onCollapse: () => void;
  onModeChange: (mode: NavigationMode) => void;
}

/**
 * The chat state used to arrive here as five props threaded from the rail. It
 * does not any more: the panel reads the conversation from `ChatProvider`, and
 * this component only needs `send` for the search panel's *Ask PropAI* button —
 * the one place outside the panel that starts a turn.
 */
export function NavigationExpanded({ activeId, items, account, mode, onCollapse, onModeChange }: NavigationExpandedProps) {
  const { send } = useChat();
  return (
    <div className="flex h-full min-w-0 max-w-full flex-col gap-3.5 overflow-hidden px-4 py-2.5">
      <header className="grid shrink-0 gap-3">
        <NavigationBrandHeader onCollapse={onCollapse} />
        <NavigationModeTabs mode={mode} onModeChange={onModeChange} />
      </header>
      <div className="relative min-h-0 min-w-0 max-w-full flex-1 overflow-hidden">
        <div className={mode === 'home' ? 'h-full' : 'hidden'}><NavigationHomePanel activeId={activeId} items={items} account={account} /></div>
        <div className={mode === 'chat' ? 'h-full' : 'hidden'}><NavigationChatPanel /></div>
        <div className={mode === 'notifications' ? 'h-full' : 'hidden'}><NavigationUpdatesPanel /></div>
        <div className={mode === 'search' ? 'h-full' : 'hidden'}><NavigationSearchPanel onAskPropAI={(query) => { onModeChange('chat'); if (query) send(query); else requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('[data-navigation-chat-input]')?.focus()); }} /></div>
      </div>
    </div>
  );
}
