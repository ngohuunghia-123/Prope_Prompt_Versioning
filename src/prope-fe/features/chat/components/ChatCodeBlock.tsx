import { Check, Copy } from '@phosphor-icons/react';
import { useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export function ChatCodeBlock({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const copy = () => {
    const text = ref.current?.textContent ?? '';
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_500);
    });
  };

  return (
    <div className="relative my-2 overflow-hidden rounded-navigation-panel bg-ink text-canvas">
      <button type="button" onClick={copy} aria-label={t('chat.actions.copyCode')} className="absolute right-2 top-2 grid size-8 cursor-pointer place-items-center rounded-full bg-surface text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
        {copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />}
      </button>
      <pre ref={ref} className="overflow-x-auto p-3 pr-12 text-overline"><code>{children}</code></pre>
    </div>
  );
}
