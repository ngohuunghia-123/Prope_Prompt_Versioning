import { useContext } from 'react';
import { DashboardFilterContext } from './dashboardFilterContextValue';
import type { DashboardFilterApi } from './dashboardFilterTypes';

export function useDashboardFilter(): DashboardFilterApi {
  const ctx = useContext(DashboardFilterContext);
  if (!ctx) throw new Error('useDashboardFilter must be used inside <DashboardFilterProvider>');
  return ctx;
}