import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { ContentSkeleton } from '@/components/ui/ContentSkeleton';
import { sessionOptions } from '@/features/auth/queries';
import { getChangePasswordPath, getLoginPath, sanitizeReturnTo } from '@/features/auth/returnTo';

export interface AuthRouteProps { children: ReactNode; }

export function AuthRoute({ children }: AuthRouteProps) {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  const location = useLocation();
  const returnTo = sanitizeReturnTo(`${location.pathname}${location.search}${location.hash}`);
  if (session.isPending) return <ContentSkeleton label={t('common.loading')} layout="page" className="min-h-dvh bg-canvas p-6 lg:p-8" />;
  if (session.isError) {
    return (
      <main className="grid min-h-dvh place-items-center bg-canvas p-4">
        <div className="max-w-auth rounded-visual border border-border bg-surface p-6 text-center shadow-floating">
          <p role="alert" className="text-body text-danger-text">{t('auth.sessionCheckError')}</p>
          <Button className="mt-4" type="button" intent="neutral" onClick={() => void session.refetch()}>{t('common.tryAgain')}</Button>
        </div>
      </main>
    );
  }
  if (!session.data) return <Navigate to={getLoginPath(returnTo)} replace />;
  if (session.data.mustChangePassword) return <Navigate to={getChangePasswordPath(returnTo)} replace />;
  // ADR-0056. A session may name no workspace, and every screen under `/app`
  // reads one — the key routes are addressed by it and the prompt list is
  // tenant-scoped underneath. So the lobby is a redirect rather than a rendered
  // empty state: a person who belongs nowhere has nothing to look at here, and
  // the chooser is where they get somewhere.
  //
  // Ordered after `mustChangePassword` deliberately. A-110's forced change is
  // about the credential, which has to be settled before anything else — and the
  // change-password screen is reachable from a lobby session, because a person
  // an Admin created and has not yet approved still has to be able to set their
  // own password.
  if (!session.data.user.workspaceId) return <Navigate to="/workspaces" replace />;
  return children;
}
