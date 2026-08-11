import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { sessionOptions } from '@/features/auth/queries';

export interface AuthRouteProps { children: ReactNode; }

export function AuthRoute({ children }: AuthRouteProps) {
  const { t } = useTranslation();
  const session = useQuery(sessionOptions);
  const location = useLocation();
  if (session.isPending) return <div className="grid min-h-dvh place-items-center text-body text-muted">{t('common.loading')}</div>;
  if (!session.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
