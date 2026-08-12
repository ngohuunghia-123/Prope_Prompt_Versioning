import { Link } from 'react-router-dom';
import { Tooltip } from '@/components/ui/Tooltip';
import { useWorkspaceAccountIdentity } from '@/features/auth/components/useWorkspaceAccountIdentity';

export function WorkspaceCompactAccount() {
  const { initials, name } = useWorkspaceAccountIdentity();
  const account = <Link to="/app/account" aria-label={name} className="grid size-8 place-items-center rounded-full bg-navigation-avatar text-overline font-bold text-ink focus-visible:outline-2 focus-visible:outline-focus">{initials}</Link>;
  return <Tooltip label={name} side="right">{account}</Tooltip>;
}
