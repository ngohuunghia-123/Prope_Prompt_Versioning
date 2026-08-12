import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { getLoginPath, sanitizeReturnTo } from '@/features/auth/returnTo';
import { setUnauthorizedHandler } from '@/lib/apiClient';

export function AuthSessionListener() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      const returnTo = sanitizeReturnTo(`${location.pathname}${location.search}${location.hash}`);
      queryClient.clear();
      void navigate(getLoginPath(returnTo), { replace: true, state: { sessionExpired: true } });
    });
    return () => setUnauthorizedHandler();
  }, [location.hash, location.pathname, location.search, navigate, queryClient]);

  return null;
}
