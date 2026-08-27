import { gsap } from 'gsap';

export type MotionPreset = 'surface' | 'modal' | 'popover' | 'tooltip-top' | 'tooltip-right' | 'drawer-left' | 'drawer-right' | 'sheet-bottom' | 'toast' | 'row';

function cssToken(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function seconds(name: string) {
  const value = cssToken(name);
  const duration = Number.parseFloat(value);
  return value.endsWith('ms') ? duration / 1000 : duration;
}

function distance() {
  return Number.parseFloat(cssToken('--prope-motion-distance-enter'));
}

export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function hiddenState(preset: MotionPreset): gsap.TweenVars {
  const offset = distance();
  if (preset === 'modal') return { autoAlpha: 0, y: offset, scale: 0.98 };
  if (preset === 'drawer-left') return { autoAlpha: 0, x: -offset };
  if (preset === 'drawer-right') return { autoAlpha: 0, x: offset };
  if (preset === 'sheet-bottom') return { autoAlpha: 0, yPercent: 100 };
  if (preset === 'toast') return { autoAlpha: 0, x: offset };
  if (preset === 'popover') return { autoAlpha: 0, y: -(offset / 2) };
  if (preset === 'tooltip-top') return { autoAlpha: 0, y: offset / 2 };
  if (preset === 'tooltip-right') return { autoAlpha: 0, x: -(offset / 2) };
  return { autoAlpha: 0, y: offset };
}

function visibleState(preset: MotionPreset): gsap.TweenVars {
  // The bottom sheet travels on `yPercent` so its resting position is whatever
  // its own height puts it at — a pixel offset would have to be re-measured
  // every time the trace grows a row, which it does while the sheet is open.
  if (preset === 'sheet-bottom') return { autoAlpha: 1, yPercent: 0 };
  return { autoAlpha: 1, x: 0, y: 0, scale: 1 };
}

export function animatePresence(element: Element, preset: MotionPreset, entering: boolean, onComplete?: () => void) {
  if (prefersReducedMotion()) {
    const tween = gsap.set(element, entering ? visibleState(preset) : hiddenState(preset));
    onComplete?.();
    return tween;
  }
  const fastEntry = preset === 'popover' || preset.startsWith('tooltip') || preset === 'row';
  const duration = seconds(entering && !fastEntry ? '--prope-motion-duration-base' : '--prope-motion-duration-fast');
  const ease = cssToken(entering && preset === 'modal' ? '--prope-motion-ease-emphasized' : '--prope-motion-ease-standard');
  return entering
    ? gsap.fromTo(element, hiddenState(preset), { ...visibleState(preset), duration, ease, overwrite: 'auto', onComplete })
    : gsap.to(element, { ...hiddenState(preset), duration, ease, overwrite: 'auto', onComplete });
}

export function animateBackdrop(element: Element, entering: boolean) {
  if (prefersReducedMotion()) return gsap.set(element, { autoAlpha: entering ? 1 : 0 });
  return gsap.to(element, {
    autoAlpha: entering ? 1 : 0,
    duration: seconds(entering ? '--prope-motion-duration-base' : '--prope-motion-duration-fast'),
    ease: cssToken('--prope-motion-ease-standard'),
  });
}

export function animateNavigationSwap(outgoing: Element, incoming: Element, forward: boolean, onComplete: () => void) {
  if (prefersReducedMotion()) {
    gsap.set(outgoing, { autoAlpha: 0 });
    gsap.set(incoming, { autoAlpha: 1 });
    onComplete();
    return;
  }

  const direction = forward ? 1 : -1;
  const duration = seconds('--prope-motion-duration-base');
  const ease = cssToken('--prope-motion-ease-standard');
  const timeline = gsap.timeline({ defaults: { duration, ease, overwrite: 'auto' }, onComplete });
  timeline
    .fromTo(outgoing, { xPercent: 0 }, { xPercent: -100 * direction })
    .fromTo(incoming, { xPercent: 100 * direction }, { xPercent: 0 }, '<');
}

export function enterSurface(element: Element) {
  // A zero-valued transform still establishes a containing block for fixed
  // descendants. Leaving GSAP's `translate(0, 0)` on the page surface made
  // shared fixed UI such as BottomActionDock anchor to a centered form instead
  // of the viewport/content panel. Clear only the transform after entry; the
  // final opacity remains in place and future route entries can animate again.
  return animatePresence(element, 'surface', true, () => {
    gsap.set(element, { clearProps: 'transform' });
  });
}
