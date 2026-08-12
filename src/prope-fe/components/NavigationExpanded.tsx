import type { ReactNode } from 'react';
import { NavigationBrandHeader } from '@/components/NavigationBrandHeader';
import { NavigationChatPanel } from '@/components/NavigationChatPanel';
import { NavigationHomePanel } from '@/components/NavigationHomePanel';
import { NavigationModeTabs } from '@/components/NavigationModeTabs';
import { NavigationSearchPanel } from '@/components/NavigationSearchPanel';
import { NavigationUpdatesPanel } from '@/components/NavigationUpdatesPanel';
import type { NavigationItem } from '@/components/NavigationMenu';
import type { NavigationMessage, NavigationMode } from '@/components/navigationTypes';

export interface NavigationExpandedProps {
  activeId: string;
  items?: NavigationItem[];
  account?: ReactNode;
  mode: NavigationMode;
  chatInput: string;
  messages: NavigationMessage[];
  thinking: boolean;
  onCollapse: () => void;
  onModeChange: (mode: NavigationMode) => void;
  onChatInputChange: (value: string) => void;
  onSendMessage: (text?: string) => void;
}

export function NavigationExpanded({ activeId, items, account, mode, chatInput, messages, thinking, onCollapse, onModeChange, onChatInputChange, onSendMessage }: NavigationExpandedProps) {
  return (
    <div className="flex h-full min-w-0 max-w-full flex-col gap-3.5 overflow-hidden px-4 py-2.5">
      <header className="grid shrink-0 gap-3">
        <NavigationBrandHeader onCollapse={onCollapse} />
        <NavigationModeTabs mode={mode} onModeChange={onModeChange} />
      </header>
      <div className="relative min-h-0 min-w-0 max-w-full flex-1 overflow-hidden">
        <div className={mode === 'home' ? 'h-full' : 'hidden'}><NavigationHomePanel activeId={activeId} items={items} account={account} /></div>
        <div className={mode === 'chat' ? 'h-full' : 'hidden'}><NavigationChatPanel input={chatInput} messages={messages} thinking={thinking} onInputChange={onChatInputChange} onSend={() => onSendMessage()} /></div>
        <div className={mode === 'notifications' ? 'h-full' : 'hidden'}><NavigationUpdatesPanel /></div>
        <div className={mode === 'search' ? 'h-full' : 'hidden'}><NavigationSearchPanel onAskPropAI={(query) => { onModeChange('chat'); if (query) onSendMessage(query); else requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('[data-navigation-chat-input]')?.focus()); }} /></div>
      </div>
    </div>
  );
}
