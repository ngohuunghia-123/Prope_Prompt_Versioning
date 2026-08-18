import { CaretDown, Check } from '@phosphor-icons/react';
import { useId, useState, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

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
  onValueChange?: (value: string) => void;
}

export function Select({ label, labelHidden = false, options, name, id, value, defaultValue = '', error, disabled = false, className, leadingIcon, selectedLabel, onValueChange }: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const listboxId = `${selectId}-listbox`;
  const [open, setOpen] = useState(false);
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const selectedValue = value ?? uncontrolledValue;
  const selectedOption = options.find((option) => option.value === selectedValue);

  const chooseOption = (option: SelectOption) => {
    if (option.disabled) return;
    if (value === undefined) setUncontrolledValue(option.value);
    onValueChange?.(option.value);
    setOpen(false);
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
        {open ? (
          <ul id={listboxId} role="listbox" aria-labelledby={`${selectId}-label`} className="absolute z-40 mt-2 max-h-60 w-full overflow-auto rounded-notification border border-border bg-surface p-1 shadow-floating">
            {options.map((option) => (
              <li key={option.value} role="option" aria-selected={option.value === selectedValue}>
                <button type="button" disabled={option.disabled} onClick={() => chooseOption(option)} className="flex min-h-10 w-full items-center justify-between gap-3 rounded-control px-3 text-left text-body text-ink hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:text-disabled-text">
                  <span>{option.label}</span>
                  {option.value === selectedValue ? <Check aria-hidden weight="bold" className="size-4 text-secondary" /> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {error ? <span className="text-caption font-normal text-danger-text">{error}</span> : null}
    </div>
  );
}
