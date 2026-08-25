import { ArrowLeft, ArrowRight, MapTrifold, X } from '@phosphor-icons/react';
import { createPortal } from 'react-dom';
import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { useDialogFocus } from '@/components/ui/useDialogFocus';
import type { ProductTourStep } from '@/features/product-tour/productTourSteps';
import type { ProductTourTargetRect } from '@/features/product-tour/useProductTourTarget';

interface ProductTourOverlayProps {
  step: ProductTourStep;
  stepIndex: number;
  total: number;
  target: ProductTourTargetRect;
  onBack: () => void;
  onNext: () => void;
  onSkip: () => void;
}

const VIEWPORT_GAP = 16;
const TARGET_GAP = 12;
const TARGET_PADDING = 8;

function tooltipPosition(target: ProductTourTargetRect, size: { width: number; height: number }) {
  const width = Math.min(size.width, window.innerWidth - VIEWPORT_GAP * 2);
  const centered = target.x + target.width / 2 - width / 2;
  const left = Math.max(VIEWPORT_GAP, Math.min(centered, window.innerWidth - width - VIEWPORT_GAP));
  const below = target.y + target.height + TARGET_GAP;
  const top = below + size.height <= window.innerHeight - VIEWPORT_GAP
    ? below
    : Math.max(VIEWPORT_GAP, target.y - size.height - TARGET_GAP);
  return { left, top };
}

export function ProductTourOverlay({ step, stepIndex, total, target, onBack, onNext, onSkip }: ProductTourOverlayProps) {
  const { t } = useTranslation();
  const dialogRef = useDialogFocus(true, onSkip, '[data-tour-primary]');
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const [surfaceSize, setSurfaceSize] = useState({ width: 336, height: 260 });
  const padded = {
    x: Math.max(0, target.x - TARGET_PADDING),
    y: Math.max(0, target.y - TARGET_PADDING),
    width: Math.min(window.innerWidth - Math.max(0, target.x - TARGET_PADDING), target.width + TARGET_PADDING * 2),
    height: Math.min(window.innerHeight - Math.max(0, target.y - TARGET_PADDING), target.height + TARGET_PADDING * 2),
  };
  const position = tooltipPosition(target, surfaceSize);
  const last = stepIndex === total - 1;

  useLayoutEffect(() => {
    if (!surfaceRef.current) return;
    const surface = surfaceRef.current;
    const update = () => setSurfaceSize({ width: surface.offsetWidth, height: surface.offsetHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(surface);
    return () => observer.disconnect();
  }, [step.id]);

  return createPortal(
    <div className="fixed inset-0 z-product-tour" aria-live="polite">
      <svg aria-hidden className="absolute inset-0 size-full text-ink/55">
        <defs>
          <mask id="product-tour-spotlight" maskUnits="userSpaceOnUse" x="0" y="0" width="100%" height="100%">
            <rect width="100%" height="100%" fill="white" />
            <rect x={padded.x} y={padded.y} width={padded.width} height={padded.height} rx="14" fill="black" />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="currentColor" mask="url(#product-tour-spotlight)" />
      </svg>
      <div
        ref={(node) => { surfaceRef.current = node; dialogRef.current = node; }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-tour-title"
        aria-describedby="product-tour-body"
        className="fixed w-(--container-product-tour) animate-navigation-panel rounded-modal border border-border bg-surface p-5 text-ink shadow-floating motion-reduce:animate-none"
        style={position}
      >
        <div className="flex items-start justify-between gap-3">
          <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-secondary"><MapTrifold className="size-5" weight="fill" /></span>
          <Button type="button" intent="ghost" size="navigationIcon" onClick={onSkip} aria-label={t('lifecycle.productTour.skip')} className="rounded-full"><X aria-hidden /></Button>
        </div>
        <p className="mt-4 text-overline font-bold uppercase tracking-navigation-overline text-navigation-overline">{t('lifecycle.productTour.progress', { current: stepIndex + 1, total })}</p>
        <h2 id="product-tour-title" className="mt-1 font-display text-heading-3 text-ink">{t(step.titleKey)}</h2>
        <p id="product-tour-body" className="mt-2 text-body text-muted">{t(step.bodyKey)}</p>
        <div aria-hidden className="mt-4 flex gap-1.5">
          {Array.from({ length: total }, (_, index) => <span key={index} className={index === stepIndex ? 'h-1.5 w-5 rounded-full bg-secondary' : 'size-1.5 rounded-full bg-border'} />)}
        </div>
        <div className="mt-5 flex items-center justify-between gap-2">
          <Button type="button" intent="ghost" size="small" onClick={onSkip}>{t('lifecycle.productTour.skip')}</Button>
          <div className="flex gap-2">
            <Button type="button" intent="neutral" size="small" leadingIcon={<ArrowLeft aria-hidden className="size-4" />} disabled={stepIndex === 0} onClick={onBack}>{t('lifecycle.productTour.back')}</Button>
            <Button type="button" data-tour-primary size="small" trailingIcon={last ? undefined : <ArrowRight aria-hidden className="size-4" />} onClick={onNext}>{t(last ? 'lifecycle.productTour.finish' : 'lifecycle.productTour.next')}</Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
