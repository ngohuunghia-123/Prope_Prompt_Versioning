import { ChatMarkdown } from '@/features/chat/components/ChatMarkdown';

export function ChatUserMessage({ text }: { text: string }) {
  return (
    <div className="max-w-[var(--prope-navigation-message-max-width)] animate-navigation-message self-end rounded-navigation-panel bg-surface px-2.5 py-2 text-ink shadow-inset">
      <ChatMarkdown>{text}</ChatMarkdown>
    </div>
  );
}
