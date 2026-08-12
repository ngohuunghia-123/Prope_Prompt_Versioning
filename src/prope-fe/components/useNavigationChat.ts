import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { NavigationMessage } from '@/components/navigationTypes';

export function useNavigationChat() {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<NavigationMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const nextId = useRef(0);
  const replyTimeout = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(replyTimeout.current), []);

  const sendMessage = useCallback((providedText?: string) => {
    const text = (providedText ?? input).trim();
    if (!text) return;
    setMessages((current) => [...current, { id: nextId.current++, role: 'user', text }]);
    setInput('');
    setThinking(true);
    window.clearTimeout(replyTimeout.current);
    replyTimeout.current = window.setTimeout(() => {
      setMessages((current) => [...current, { id: nextId.current++, role: 'agent', text: t('navigation.advanced.chat.agentReply') }]);
      setThinking(false);
    }, 520);
  }, [input, t]);

  return { input, setInput, messages, thinking, sendMessage };
}
