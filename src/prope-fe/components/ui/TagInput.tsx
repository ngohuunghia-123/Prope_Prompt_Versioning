import { Check, Plus, X } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { Input } from '@/components/ui/Input';
import { Tag } from '@/components/Tag';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

interface TagInputProps {
  label: string;
  labelHidden?: boolean;
  placeholder: string;
  createLabel: (tag: string) => string;
  values: string[];
  onChange: (values: string[]) => void;
  removeLabel: (tag: string) => string;
  options?: string[];
  systemTags?: string[];
  max?: number;
  menuLayout?: 'floating' | 'inline';
}

export function TagInput({ label, labelHidden = false, placeholder, createLabel, values, onChange, removeLabel, options = [], systemTags = [], max = 10, menuLayout = 'floating' }: TagInputProps) {
  const [draft, setDraft] = useState('');
  const [open, setOpen] = useState(false);
  const candidate = draft.trim().replace(/^#+/, '');
  const normalizedCandidate = candidate.toLocaleLowerCase();
  const available = [...new Set(options)]
    .filter((option) => !values.some((value) => value.toLocaleLowerCase() === option.toLocaleLowerCase()))
    .filter((option) => normalizedCandidate === '' || option.toLocaleLowerCase().includes(normalizedCandidate));
  const existingCandidate = options.some((option) => option.toLocaleLowerCase() === normalizedCandidate);
  const canAdd = candidate.length > 0
    && candidate.length <= 32
    && values.length < max
    && !values.some((value) => value.toLocaleLowerCase() === normalizedCandidate);
  const hasMenu = open && (available.length > 0 || (canAdd && !existingCandidate));
  const motion = useMotionPresence(hasMenu, 'popover');

  const add = () => {
    if (!canAdd) return;
    onChange([...values, candidate]);
    setDraft('');
    setOpen(false);
  };

  const choose = (tag: string) => {
    if (values.length >= max) return;
    onChange([...values, tag]);
    setDraft('');
    setOpen(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' && event.key !== ',') return;
    event.preventDefault();
    add();
  };

  return (
    <div className="grid gap-2" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <div className="relative min-w-0">
          <Input className="min-w-0" label={label} labelHidden={labelHidden} placeholder={placeholder} value={draft} maxLength={32} onFocus={() => setOpen(true)} onChange={(event) => { setDraft(event.currentTarget.value); setOpen(true); }} onKeyDown={onKeyDown} />
          {motion.mounted ? (
            <ul
              ref={(node) => { motion.surfaceRef.current = node; }}
              role="listbox"
              aria-label={label}
              className={cn(
                'mt-2 max-h-60 w-full overflow-auto rounded-notification border border-border bg-surface p-1 shadow-floating',
                menuLayout === 'floating' ? 'absolute z-40' : 'relative',
                !hasMenu && 'pointer-events-none',
              )}
            >
              {available.map((tag) => (
                <li key={tag} role="option" aria-selected={false}>
                  <button type="button" onClick={() => choose(tag)} className="flex min-h-10 w-full items-center justify-between gap-3 rounded-control px-3 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
                    <span>{tag}</span>
                    <Check aria-hidden className="size-4 text-muted" />
                  </button>
                </li>
              ))}
              {canAdd && !existingCandidate ? (
                <li role="option" aria-selected={false}>
                  <button type="button" onClick={add} className="flex min-h-10 w-full items-center gap-3 rounded-control px-3 text-left text-body text-link hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus">
                    <Plus aria-hidden className="size-4" />
                    <span>{createLabel(candidate)}</span>
                  </button>
                </li>
              ) : null}
            </ul>
          ) : null}
      </div>
      {values.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {values.map((tag) => (
            <Tag key={tag} state={systemTags.some((systemTag) => systemTag.toLocaleLowerCase() === tag.toLocaleLowerCase()) ? 'default' : 'neutral'} className="gap-1">
              <span className="max-w-48 truncate">{tag}</span>
              <button type="button" className="cursor-pointer rounded-full text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus" aria-label={removeLabel(tag)} onClick={() => onChange(values.filter((value) => value !== tag))}><X aria-hidden className="size-3" /></button>
            </Tag>
          ))}
        </div>
      ) : null}
    </div>
  );
}
