import { createContext } from 'react';
import type { DashboardFilterApi } from './dashboardFilterTypes';

export const DashboardFilterContext = createContext<DashboardFilterApi | null>(null);