import { cn } from '@/lib/cn';

interface WordHeatmapProps {
  text: string;
  sharedWords: Set<string>;
  className?: string;
}

/** Renders text with the words of `sharedWords` highlighted, whitespace preserved. */
export function WordHeatmap({ text, sharedWords, className }: WordHeatmapProps) {
  return (
    <p className={cn('whitespace-pre-wrap leading-relaxed text-ink', className)}>
      {text.split(/(\s+)/).map((part, index) => (
        sharedWords.has(part.toLocaleLowerCase().replace(/[^\p{L}\p{N}_-]/gu, ''))
          ? <mark key={`${part}-${index}`} className="rounded-control bg-secondary/20 px-0.5 text-ink">{part}</mark>
          : <span key={`${part}-${index}`}>{part}</span>
      ))}
    </p>
  );
}
