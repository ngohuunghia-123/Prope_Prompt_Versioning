import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { sessionOptions } from '@/features/auth/queries';
import { getChangePasswordPath, getLoginPath, sanitizeReturnTo } from '@/features/auth/returnTo';

export interface AuthRouteProps { children: ReactNode; }

export function AuthRoute({ children }: AuthRouteProps) {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  const location = useLocation();
  const returnTo = sanitizeReturnTo(`${location.pathname}${location.search}${location.hash}`);
  if (session.isPending) return <div className="grid min-h-dvh place-items-center bg-canvas text-body text-muted">{t('common.loading')}</div>;
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
  return children;
}
