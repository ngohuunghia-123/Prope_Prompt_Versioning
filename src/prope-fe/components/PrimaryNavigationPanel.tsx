import type { NavigationItem } from '@/components/NavigationMenu';
import { NavigationChatPanel } from '@/components/NavigationChatPanel';
import { NavigationHomePanel } from '@/components/NavigationHomePanel';
import { NavigationModeTabs } from '@/components/NavigationModeTabs';
import { NavigationSearchPanel } from '@/components/NavigationSearchPanel';
import { NavigationUpdatesPanel } from '@/components/NavigationUpdatesPanel';
import type { NavigationMode } from '@/components/navigationTypes';
import { useChat } from '@/features/chat/ChatContext';

export interface PrimaryNavigationPanelProps {
  activeId: string;
  items?: NavigationItem[];
  mode: NavigationMode;
  onModeChange: (mode: NavigationMode) => void;
}

export function PrimaryNavigationPanel({ activeId, items, mode, onModeChange }: PrimaryNavigationPanelProps) {
  const { send } = useChat();
  return (
    <div data-navigation-panel="primary" className="flex h-full min-w-0 max-w-full flex-col gap-3.5 overflow-hidden px-4 pt-3.5">
      <NavigationModeTabs mode={mode} onModeChange={onModeChange} />
      <div className="relative min-h-0 min-w-0 max-w-full flex-1 overflow-hidden">
        <div className={mode === 'home' ? 'h-full' : 'hidden'}><NavigationHomePanel activeId={activeId} items={items} showAccount={false} /></div>
        <div className={mode === 'chat' ? 'h-full' : 'hidden'}><NavigationChatPanel /></div>
        <div className={mode === 'notifications' ? 'h-full' : 'hidden'}><NavigationUpdatesPanel active={mode === 'notifications'} /></div>
        <div className={mode === 'search' ? 'h-full' : 'hidden'}><NavigationSearchPanel onAskPropAI={(query) => { onModeChange('chat'); if (query) send(query); else requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('[data-navigation-chat-input]')?.focus()); }} /></div>
      </div>
    </div>
  );
}
