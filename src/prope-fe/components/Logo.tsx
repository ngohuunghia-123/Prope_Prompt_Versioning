import { cn } from '@/lib/cn';
import { useTheme } from '@/lib/useTheme';

export interface LogoProps { variant?: 'mark' | 'full'; inverse?: boolean; className?: string; }

export function Logo({ variant = 'full', inverse = false, className }: LogoProps) {
  const { theme } = useTheme();
  const showInverse = inverse || theme === 'dark';
  return (
    <span className={cn('inline-flex items-center gap-1 text-ink', showInverse && 'text-inverse', className)}>
      <img src={showInverse ? '/assets/prope-logo-inverse.svg' : '/assets/prope-mark.svg'} alt="" className="size-10 shrink-0" />
      {variant === 'full' ? <span className="font-display text-heading-2 leading-none">Prope</span> : <span className="sr-only">Prope</span>}
    </span>
  );
}
