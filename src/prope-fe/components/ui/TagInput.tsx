import { Plus, X } from '@phosphor-icons/react';
import { useState, type KeyboardEvent } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tag } from '@/components/Tag';

interface TagInputProps {
  label: string;
  placeholder: string;
  addLabel: string;
  values: string[];
  onChange: (values: string[]) => void;
  removeLabel: (tag: string) => string;
  max?: number;
}

export function TagInput({ label, placeholder, addLabel, values, onChange, removeLabel, max = 10 }: TagInputProps) {
  const [draft, setDraft] = useState('');
  const candidate = draft.trim().replace(/^#+/, '');
  const canAdd = candidate.length > 0
    && candidate.length <= 32
    && values.length < max
    && !values.some((value) => value.toLocaleLowerCase() === candidate.toLocaleLowerCase());

  const add = () => {
    if (!canAdd) return;
    onChange([...values, candidate]);
    setDraft('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' && event.key !== ',') return;
    event.preventDefault();
    add();
  };

  return (
    <div className="grid gap-2">
      <div className="flex items-end gap-2">
        <Input className="min-w-0 flex-1" label={label} placeholder={placeholder} value={draft} maxLength={32} onChange={(event) => setDraft(event.currentTarget.value)} onKeyDown={onKeyDown} />
        <Button type="button" size="icon" intent="neutral" aria-label={addLabel} disabled={!canAdd} disabledReason={addLabel} onClick={add}><Plus aria-hidden /></Button>
      </div>
      {values.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {values.map((tag) => (
            <Tag key={tag} state="neutral" className="gap-1">
              <span className="max-w-48 truncate">{tag}</span>
              <button type="button" className="cursor-pointer rounded-full text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus" aria-label={removeLabel(tag)} onClick={() => onChange(values.filter((value) => value !== tag))}><X aria-hidden className="size-3" /></button>
            </Tag>
          ))}
        </div>
      ) : null}
    </div>
  );
}
