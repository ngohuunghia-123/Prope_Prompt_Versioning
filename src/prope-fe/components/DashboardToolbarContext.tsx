import { createContext, useContext, type ReactNode } from 'react';

export interface DashboardFilterValues {
  search: string;
  status: string;
}

export interface DashboardFilters extends DashboardFilterValues {
  setSearch: (value: string) => void;
  setStatus: (value: string) => void;
}

interface ToolbarContextValue {
  toolbarNode: ReactNode;
  setToolbarNode: (node: ReactNode) => void;
  filters: DashboardFilters;
}

const defaultFilters: DashboardFilters = {
  search: '',
  status: 'all',
  setSearch: () => undefined,
  setStatus: () => undefined,
};

export const DashboardContext = createContext<ToolbarContextValue>({
  toolbarNode: null,
  setToolbarNode: () => null,
  filters: defaultFilters,
});

export function useDashboardContext() {
  return useContext(DashboardContext);
}
