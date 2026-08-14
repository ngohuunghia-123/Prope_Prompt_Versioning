import { Funnel, MagnifyingGlass, SortAscending, X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { DashboardSort, DashboardStatusFilter } from './dashboardFilterTypes';
import { useDashboardFilter } from './useDashboardFilter';

const STATUS_VALUES: readonly DashboardStatusFilter[] = ['all', 'inUse', 'approved', 'inReview', 'draft', 'retired'];
const SORT_VALUES: readonly DashboardSort[] = ['updated', 'title', 'owner', 'status'];

function isDashboardRoute(): boolean {
  if (typeof window === 'undefined') return false;
  const path = window.location.pathname.replace(/^\/+/, '');
  if (!path.startsWith('app/prompts')) return false;
  const segments = path.split('/').filter(Boolean);
  return segments.length <= 2;
}

export function DashboardFilterBar() {
  const { t } = useTranslation();
  const { search, status, sort, setSearch, setStatus, setSort, reset } = useDashboardFilter();
  if (typeof document === 'undefined') return null;
  const target = document.getElementById('topbar-secondary');
  if (!target || !isDashboardRoute()) return null;
  const hasActiveFilter = search.length > 0 || status !== 'all' || sort !== 'updated';
  const node = (
    <div className="flex items-center gap-2" role="group" aria-label={t('lifecycle.dashboard.filter.groupLabel')}>
      <label className="relative hidden sm:block">
        <span className="sr-only">{t('lifecycle.dashboard.searchAria')}</span>
        <MagnifyingGlass aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          type="search"
          name="prompt-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('lifecycle.dashboard.searchPlaceholder')}
          aria-label={t('lifecycle.dashboard.searchAria')}
          className="h-9 w-56 rounded-lg border border-border bg-surface pl-8 pr-3 text-caption text-ink shadow-inset outline-none transition-colors placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
        />
      </label>
      <div className="hidden h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-2 sm:flex">
        <Funnel aria-hidden className="size-4 shrink-0 text-muted" />
        <span className="sr-only">{t('lifecycle.dashboard.filter.statusLabel')}</span>
        <select
          aria-label={t('lifecycle.dashboard.filter.statusLabel')}
          value={status}
          onChange={(event) => setStatus(event.target.value as DashboardStatusFilter)}
          name="prompt-status-filter"
          className="h-7 cursor-pointer appearance-none border-none bg-transparent pr-6 text-caption text-ink outline-none focus:ring-0"
          style={{ backgroundImage: 'none' }}
        >
          {STATUS_VALUES.map((value) => (
            <option key={value} value={value}>
              {value === 'all' ? t('lifecycle.dashboard.filter.statusAll') : t(`status.${value}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="hidden h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-2 sm:flex">
        <SortAscending aria-hidden className="size-4 shrink-0 text-muted" />
        <span className="sr-only">{t('lifecycle.dashboard.sort.label')}</span>
        <select
          aria-label={t('lifecycle.dashboard.sort.label')}
          value={sort}
          onChange={(event) => setSort(event.target.value as DashboardSort)}
          name="prompt-sort"
          className="h-7 cursor-pointer appearance-none border-none bg-transparent pr-6 text-caption text-ink outline-none focus:ring-0"
          style={{ backgroundImage: 'none' }}
        >
          {SORT_VALUES.map((value) => (
            <option key={value} value={value}>
              {t(`lifecycle.dashboard.sort.${value}`)}
            </option>
          ))}
        </select>
      </div>
      {hasActiveFilter ? (
        <button
          type="button"
          onClick={reset}
          aria-label={t('lifecycle.dashboard.filter.reset')}
          className="grid size-9 cursor-pointer place-items-center rounded-lg border border-border bg-surface text-muted hover:bg-subtle focus-visible:outline-2 focus-visible:outline-focus"
        >
          <X aria-hidden className="size-4" />
        </button>
      ) : null}
    </div>
  );
  return createPortal(node, target);
}
