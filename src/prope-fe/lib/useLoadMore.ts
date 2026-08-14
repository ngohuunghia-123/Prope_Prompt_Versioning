import { useEffect, useRef, useState } from 'react';

export interface UseLoadMoreOptions {
  /** Total items available in the source dataset. */
  readonly total: number;
  /** Number of items to reveal on each load-more event. */
  readonly pageSize?: number;
  /** Reset to the first page whenever any dependency in this list changes. */
  readonly resetDeps: ReadonlyArray<unknown>;
}

export interface UseLoadMoreResult {
  readonly visible: number;
  readonly hasMore: boolean;
  readonly loadMore: () => void;
  readonly reset: () => void;
}

/**
 * Headless pagination helper for lazy-loaded tables. The caller owns the
 * rendered slice (`items.slice(0, visible)`) and just watches `hasMore` /
 * calls `loadMore()`. `resetDeps` resets pagination whenever the upstream
 * filter/sort/search changes.
 */
export function useLoadMore({ total, pageSize = 10, resetDeps }: UseLoadMoreOptions): UseLoadMoreResult {
  const [visible, setVisible] = useState(pageSize);
  const lastDeps = useRef<readonly unknown[]>(resetDeps);
  useEffect(() => {
    const changed = lastDeps.current.length !== resetDeps.length
      || lastDeps.current.some((value, index) => value !== resetDeps[index]);
    if (changed) {
      lastDeps.current = resetDeps;
      setVisible(pageSize);
    }
  }, [resetDeps, pageSize]);
  const loadMore = () => {
    setVisible((current) => Math.min(total, current + pageSize));
  };
  const reset = () => setVisible(pageSize);
  return { visible, hasMore: visible < total, loadMore, reset };
}

export interface UseInfiniteScrollSentinelOptions {
  /** Element ref to observe. The sentinel must be the last element on the page. */
  readonly target: React.RefObject<Element | null>;
  readonly enabled: boolean;
  readonly onIntersect: () => void;
  /** Optional root margin override, defaults to "200px". */
  readonly rootMargin?: string;
}

/**
 * Fires `onIntersect` whenever the observed sentinel scrolls into view. Used
 * for tables that lazy-load additional rows on demand.
 */
export function useInfiniteScrollSentinel({ target, enabled, onIntersect, rootMargin = '200px' }: UseInfiniteScrollSentinelOptions): void {
  const callbackRef = useRef(onIntersect);
  callbackRef.current = onIntersect;
  useEffect(() => {
    if (!enabled) return;
    const node = target.current;
    if (!node) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) callbackRef.current();
    }, { rootMargin });
    observer.observe(node);
    return () => observer.disconnect();
  }, [target, enabled, rootMargin]);
}
