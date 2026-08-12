import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Tooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/cn';

export interface NavigationCompactItemProps {
  active: boolean;
  href: string;
  icon: ReactNode;
  label: string;
  onNavigate?: () => void;
}

export function NavigationCompactItem({ active, href, icon, label, onNavigate }: NavigationCompactItemProps) {
  const link = (
    <Link to={href} aria-label={label} aria-current={active ? 'page' : undefined} onClick={onNavigate} className={cn('grid size-8 cursor-pointer place-items-center rounded-navigation-control text-navigation-icon transition-[background-color,transform,color] duration-(--prope-motion-duration-fast) hover:scale-105 hover:bg-surface/55 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus', active && 'bg-surface text-navigation-active shadow-inset')}>
      {icon}
    </Link>
  );
  return <Tooltip label={label} side="right">{link}</Tooltip>;
}
