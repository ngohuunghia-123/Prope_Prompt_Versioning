import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useFloatingAgent } from '@/features/floating-agent/FloatingAgentContext';
import { ProductTourContext, type ProductTourContextValue } from '@/features/product-tour/ProductTourContext';
import { ProductTourOverlay } from '@/features/product-tour/ProductTourOverlay';
import { PRODUCT_TOUR_STEPS } from '@/features/product-tour/productTourSteps';
import { useProductTourTarget } from '@/features/product-tour/useProductTourTarget';

const COMPLETION_KEY = 'prope-product-tour-v1-complete';

interface ProductTourOrigin {
  href: string;
  collapsed: boolean;
  mobileOpen: boolean;
  mascotVisible: boolean;
  taskCenterExpanded: boolean;
  focus: HTMLElement | null;
}

interface ProductTourProviderProps {
  children: ReactNode;
  collapsed: boolean;
  mobileOpen: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  onMobileOpenChange: (open: boolean) => void;
}

export function ProductTourProvider({ children, collapsed, mobileOpen, onCollapsedChange, onMobileOpenChange }: ProductTourProviderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { visible, expanded, setVisible, setExpanded } = useFloatingAgent();
  const [stepIndex, setStepIndex] = useState<number | null>(null);
  const [completed, setCompleted] = useState(() => window.localStorage.getItem(COMPLETION_KEY) === 'true');
  const originRef = useRef<ProductTourOrigin | null>(null);
  const step = stepIndex === null ? undefined : PRODUCT_TOUR_STEPS[stepIndex];
  const routeReady = Boolean(step && location.pathname === step.pathname && location.hash === step.hash);

  const restore = useCallback((markCompleted: boolean) => {
    const origin = originRef.current;
    setStepIndex(null);
    if (markCompleted) {
      setCompleted(true);
      window.localStorage.setItem(COMPLETION_KEY, 'true');
    }
    if (!origin) return;
    onCollapsedChange(origin.collapsed);
    onMobileOpenChange(origin.mobileOpen);
    setVisible(origin.mascotVisible);
    setExpanded(origin.taskCenterExpanded);
    void navigate(origin.href, { replace: true });
    window.setTimeout(() => {
      const fallback = document.querySelector<HTMLElement>('[data-product-tour-launcher]');
      const target = origin.focus?.isConnected ? origin.focus : fallback;
      target?.focus();
    }, 300);
    originRef.current = null;
  }, [navigate, onCollapsedChange, onMobileOpenChange, setExpanded, setVisible]);

  const stopTour = useCallback(() => restore(false), [restore]);
  const startTour = useCallback(() => {
    if (stepIndex !== null) return;
    originRef.current = {
      href: `${location.pathname}${location.search}${location.hash}`,
      collapsed,
      mobileOpen,
      mascotVisible: visible,
      taskCenterExpanded: expanded,
      focus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
    };
    setStepIndex(0);
  }, [collapsed, expanded, location.hash, location.pathname, location.search, mobileOpen, stepIndex, visible]);

  const advancePastMissing = useCallback(() => {
    setStepIndex((current) => {
      if (current === null) return null;
      if (current < PRODUCT_TOUR_STEPS.length - 1) return current + 1;
      window.setTimeout(() => restore(false), 0);
      return current;
    });
  }, [restore]);
  const target = useProductTourTarget(step?.targetId, routeReady, advancePastMissing);

  useEffect(() => {
    if (!step) return;
    onCollapsedChange(false);
    onMobileOpenChange(step.navigationOpen);
    setExpanded(Boolean(step.expandTasks));
    if (step.expandTasks) setVisible(true);
    if (!routeReady) void navigate({ pathname: step.pathname, hash: step.hash }, { replace: true });
  }, [navigate, onCollapsedChange, onMobileOpenChange, routeReady, setExpanded, setVisible, step]);

  const next = useCallback(() => {
    if (stepIndex === null) return;
    if (stepIndex === PRODUCT_TOUR_STEPS.length - 1) restore(true);
    else setStepIndex(stepIndex + 1);
  }, [restore, stepIndex]);
  const back = useCallback(() => setStepIndex((current) => current === null ? null : Math.max(0, current - 1)), []);
  const value = useMemo<ProductTourContextValue>(() => ({ active: stepIndex !== null, completed, stepIndex, startTour, stopTour }), [completed, startTour, stepIndex, stopTour]);

  return (
    <ProductTourContext.Provider value={value}>
      {children}
      {step && stepIndex !== null && target ? <ProductTourOverlay step={step} stepIndex={stepIndex} total={PRODUCT_TOUR_STEPS.length} target={target} onBack={back} onNext={next} onSkip={stopTour} /> : null}
    </ProductTourContext.Provider>
  );
}
