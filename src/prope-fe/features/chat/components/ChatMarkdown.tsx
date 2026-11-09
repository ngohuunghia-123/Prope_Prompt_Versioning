import ReactMarkdown, { defaultUrlTransform, type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatCodeBlock } from '@/features/chat/components/ChatCodeBlock';
import { cn } from '@/lib/cn';

interface ChatMarkdownProps {
  children: string;
  className?: string;
  onCitation?: (index: number) => void;
  onOpenPrompt?: (promptId: string) => void;
}

function safeUrl(url: string): string {
  if (url.startsWith('#citation-')) return url;
  return defaultUrlTransform(url);
}

export function ChatMarkdown({ children, className, onCitation, onOpenPrompt }: ChatMarkdownProps) {
  const components: Components = {
    a: ({ href, children: label }) => {
      const citation = href?.match(/^#citation-(\d+)$/);
      if (citation) {
        return (
          <sup>
            <button type="button" onClick={() => onCitation?.(Number(citation[1]))} className="mx-0.5 cursor-pointer rounded-full bg-info px-1.5 py-0.5 font-semibold text-info-strong hover:bg-info-strong hover:text-canvas focus-visible:outline-2 focus-visible:outline-focus">
              {label}
            </button>
          </sup>
        );
      }
      const external = href?.startsWith('http://') || href?.startsWith('https://');
      const promptId = href?.match(/^\/app\/prompts\/([a-zA-Z0-9_:@.-]+)(?:\?[^#]*)?$/)?.[1];
      if (promptId && onOpenPrompt) return <button type="button" onClick={() => onOpenPrompt(promptId)} className="cursor-pointer text-link underline focus-visible:outline-2 focus-visible:outline-focus">{label}</button>;
      return <a href={href} target={external ? '_blank' : undefined} rel={external ? 'noreferrer nofollow' : undefined} className="text-link underline focus-visible:outline-2 focus-visible:outline-focus">{label}</a>;
    },
    pre: ({ children: code }) => <ChatCodeBlock>{code}</ChatCodeBlock>,
  };

  return (
    <div className={cn('grid min-w-0 max-w-full gap-1.5 break-words text-caption leading-relaxed [overflow-wrap:anywhere] [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-2 [&_h1]:font-semibold [&_h1]:text-ink [&_h2]:font-semibold [&_h2]:text-ink [&_h3]:font-semibold [&_h3]:text-ink [&_li]:ml-4 [&_ol]:list-decimal [&_p]:m-0 [&_pre]:max-w-full [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto [&_table]:border-collapse [&_td]:border [&_td]:border-border [&_td]:p-1.5 [&_th]:border [&_th]:border-border [&_th]:bg-subtle [&_th]:p-1.5 [&_ul]:list-disc', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={safeUrl} components={components}>{children}</ReactMarkdown>
    </div>
  );
}
