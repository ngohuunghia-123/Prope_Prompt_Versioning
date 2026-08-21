import { SpinnerGap } from '@phosphor-icons/react';
import type { VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { buttonVariants } from '@/components/ui/buttonVariants';

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  loading?: boolean;
  disabledReason?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { children, className, intent, size, leadingIcon, trailingIcon, loading = false, disabled, disabledReason, title, ...props },
  ref,
) {
  const { t } = useTranslation();
  const iconOnly = size === 'icon' || size === 'navigationIcon' || size === 'floatingAgentIcon';
  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ intent, size }), loading && (intent ?? 'primary') === 'primary' && 'bg-primary-loading hover:bg-primary-loading', className)}
      disabled={disabled || loading}
      title={disabled && !loading ? (disabledReason ?? t('common.disabledReason')) : title}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <SpinnerGap aria-hidden className="size-4 shrink-0 animate-spin motion-reduce:animate-none" /> : leadingIcon}
      {iconOnly ? children : <span className="min-w-0 truncate">{children}</span>}
      {!loading && trailingIcon}
    </button>
  );
});
