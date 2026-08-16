import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

interface TopBarActionsProps {
  children: ReactNode;
}

export function TopBarActions({ children }: TopBarActionsProps) {
  const target = document.getElementById('topbar-actions');
  return target ? createPortal(children, target) : null;
}
