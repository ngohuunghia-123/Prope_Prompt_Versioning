import { createContext, useContext } from 'react';

export interface ProductTourContextValue {
  active: boolean;
  completed: boolean;
  stepIndex: number | null;
  startTour: () => void;
  stopTour: () => void;
}

export const ProductTourContext = createContext<ProductTourContextValue | null>(null);

export function useProductTour() {
  const value = useContext(ProductTourContext);
  if (!value) throw new Error('useProductTour must be used within ProductTourProvider');
  return value;
}
