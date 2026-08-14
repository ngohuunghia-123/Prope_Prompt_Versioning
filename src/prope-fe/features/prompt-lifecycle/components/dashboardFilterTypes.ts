export type DashboardStatusFilter = 'all' | 'draft' | 'inReview' | 'approved' | 'inUse' | 'retired';
export type DashboardSort = 'updated' | 'title' | 'owner' | 'status';

export interface DashboardFilterState {
  readonly search: string;
  readonly status: DashboardStatusFilter;
  readonly sort: DashboardSort;
}

export interface DashboardFilterApi extends DashboardFilterState {
  setSearch: (value: string) => void;
  setStatus: (value: DashboardStatusFilter) => void;
  setSort: (value: DashboardSort) => void;
  reset: () => void;
}

export const DASHBOARD_FILTER_DEFAULTS: DashboardFilterState = { search: '', status: 'all', sort: 'updated' };