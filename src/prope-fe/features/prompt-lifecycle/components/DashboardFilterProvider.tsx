import { useMemo, useState, type ReactNode } from 'react';
import { DashboardFilterContext } from './dashboardFilterContextValue';
import { DASHBOARD_FILTER_DEFAULTS } from './dashboardFilterTypes';
import type { DashboardFilterApi, DashboardSort, DashboardStatusFilter } from './dashboardFilterTypes';

export function DashboardFilterProvider({ children }: { children: ReactNode }) {
  const [search, setSearch] = useState<string>(DASHBOARD_FILTER_DEFAULTS.search);
  const [status, setStatus] = useState<DashboardStatusFilter>(DASHBOARD_FILTER_DEFAULTS.status);
  const [sort, setSort] = useState<DashboardSort>(DASHBOARD_FILTER_DEFAULTS.sort);
  const value = useMemo<DashboardFilterApi>(() => ({
    search,
    status,
    sort,
    setSearch,
    setStatus,
    setSort,
    reset: () => {
      setSearch(DASHBOARD_FILTER_DEFAULTS.search);
      setStatus(DASHBOARD_FILTER_DEFAULTS.status);
      setSort(DASHBOARD_FILTER_DEFAULTS.sort);
    },
  }), [search, status, sort]);
  return <DashboardFilterContext.Provider value={value}>{children}</DashboardFilterContext.Provider>;
}