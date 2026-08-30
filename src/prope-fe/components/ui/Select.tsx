import { CaretDown, Check, MagnifyingGlass } from '@phosphor-icons/react';
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Input } from '@/components/ui/Input';
import { cn } from '@/lib/cn';
import { useMotionPresence } from '@/lib/useMotionPresence';

export interface SelectOption { value: string; label: string; disabled?: boolean; }
export interface SelectProps {
  label: string;
  labelHidden?: boolean;
  options: SelectOption[];
  name?: string;
  id?: string;
  value?: string;
  defaultValue?: string;
  error?: string;
  disabled?: boolean;
  className?: string;
  leadingIcon?: ReactNode;
  selectedLabel?: string;
  searchable?: boolean;
  searchPlaceholder?: string;
  noMatchesLabel?: string;
  onValueChange?: (value: string) => void;
}

export function Select({ label, labelHidden = false, options, name, id, value, defaultValue = '', error, disabled = false, className, leadingIcon, selectedLabel, searchable = false, searchPlaceholder, noMatchesLabel, onValueChange }: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const listboxId = `${selectId}-listbox`;
  const [open, setOpen] = useState(false);
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const [query, setQuery] = useState('');
  const motion = useMotionPresence(open, 'popover');
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selectedValue = value ?? uncontrolledValue;
  const selectedOption = options.find((option) => option.value === selectedValue);

  const normalizedQuery = query.trim().toLowerCase();
  const visibleOptions = searchable && normalizedQuery
    ? options.filter((option) =>
        option.label.toLowerCase().includes(normalizedQuery)
        || option.value.toLowerCase().includes(normalizedQuery))
    : options;

  useEffect(() => {
    if (open) {
      if (searchable) searchRef.current?.focus();
      return;
    }
    setQuery('');
  }, [open, searchable]);

  const chooseOption = (option: SelectOption) => {
    if (option.disabled) return;
    if (value === undefined) setUncontrolledValue(option.value);
    onValueChange?.(option.value);
    setOpen(false);
  };

  const closeAndRefocus = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Escape') setOpen(false);
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setOpen(true);
    }
  };

  return (
    <div className="flex min-w-0 flex-col gap-2 text-body font-medium text-ink" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <span id={`${selectId}-label`} className={cn(labelHidden && 'sr-only')}>{label}</span>
      <div className="relative">
        <button
          ref={triggerRef}
          id={selectId}
          type="button"
          name={name}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-labelledby={`${selectId}-label`}
          aria-controls={listboxId}
          aria-expanded={open}
          aria-haspopup="listbox"
          onClick={() => setOpen((current) => !current)}
          onKeyDown={onKeyDown}
          className={cn('flex h-11 w-full cursor-pointer items-center justify-between rounded-lg border border-border bg-surface px-3 text-left text-body font-normal text-ink shadow-inset outline-none transition-colors duration-(--prope-motion-duration-fast) focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:border-border-disabled disabled:bg-disabled disabled:text-disabled-text', error && 'border-danger-strong focus:border-danger-strong focus:ring-danger-strong/25', className)}
        >
          <span className="flex items-center gap-2 truncate">
            {leadingIcon ? <span className="shrink-0 text-muted">{leadingIcon}</span> : null}
            <span className={cn('truncate', !selectedOption && 'text-muted')}>{selectedLabel ?? selectedOption?.label ?? options[0]?.label}</span>
          </span>
          <CaretDown aria-hidden className={cn('size-4 shrink-0 text-muted transition-transform', open && 'rotate-180')} />
        </button>
        {motion.mounted ? (
          <div ref={(node) => { motion.surfaceRef.current = node; }} className={cn('absolute z-40 mt-2 w-full rounded-notification border border-border bg-surface p-1 shadow-floating', !open && 'pointer-events-none')}>
            {searchable ? (
              <div className="pb-1">
                <Input
                  ref={searchRef}
                  label={searchPlaceholder ?? label}
                  labelHidden
                  placeholder={searchPlaceholder}
                  leadingIcon={<MagnifyingGlass aria-hidden className="size-4" />}
                  value={query}
                  spellCheck={false}
                  autoComplete="off"
                  className="h-9 bg-subtle"
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                      event.stopPropagation();
                      closeAndRefocus();
                    }
                  }}
                />
              </div>
            ) : null}
            <ul id={listboxId} role="listbox" aria-labelledby={`${selectId}-label`} className="max-h-60 overflow-auto rounded-notification">
              {visibleOptions.map((option) => (
                <li key={option.value} role="option" aria-selected={option.value === selectedValue}>
                  <button type="button" disabled={option.disabled} onClick={() => chooseOption(option)} className="flex min-h-10 w-full items-center justify-between gap-3 rounded-control px-3 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-disabled-text">
                    <span>{option.label}</span>
                    {option.value === selectedValue ? <Check aria-hidden weight="bold" className="size-4 text-secondary" /> : null}
                  </button>
                </li>
              ))}
            </ul>
            {visibleOptions.length === 0 && noMatchesLabel ? (
              <p role="status" className="px-3 py-2 text-caption font-normal text-muted">{noMatchesLabel}</p>
            ) : null}
          </div>
        ) : null}
      </div>
      {error ? <span className="text-caption font-normal text-danger-text">{error}</span> : null}
    </div>
  );
}
