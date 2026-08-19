import { gsap } from 'gsap';

export type MotionPreset = 'surface' | 'modal' | 'popover' | 'drawer-left' | 'drawer-right' | 'toast' | 'row';

function cssToken(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function seconds(name: string) {
  return Number.parseFloat(cssToken(name)) / 1000;
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
  if (preset === 'drawer-left') return { autoAlpha: 0, xPercent: -100 };
  if (preset === 'drawer-right') return { autoAlpha: 0, xPercent: 100 };
  if (preset === 'toast') return { autoAlpha: 0, x: offset };
  if (preset === 'popover') return { autoAlpha: 0, y: Math.max(4, offset / 2), scale: 0.99 };
  return { autoAlpha: 0, y: offset };
}

function visibleState(preset: MotionPreset): gsap.TweenVars {
  return preset.startsWith('drawer')
    ? { autoAlpha: 1, xPercent: 0 }
    : { autoAlpha: 1, x: 0, y: 0, scale: 1 };
}

export function animatePresence(element: Element, preset: MotionPreset, entering: boolean, onComplete?: () => void) {
  if (prefersReducedMotion()) {
    const tween = gsap.set(element, entering ? visibleState(preset) : hiddenState(preset));
    onComplete?.();
    return tween;
  }
  const fastEntry = preset === 'popover' || preset === 'row';
  const duration = seconds(entering && !fastEntry ? '--prope-motion-duration-base' : '--prope-motion-duration-fast');
  const ease = cssToken(entering && preset === 'modal' ? '--prope-motion-ease-emphasized' : '--prope-motion-ease-standard');
  return entering
    ? gsap.fromTo(element, hiddenState(preset), { ...visibleState(preset), duration, ease, onComplete })
    : gsap.to(element, { ...hiddenState(preset), duration, ease, onComplete });
}

export function animateBackdrop(element: Element, entering: boolean) {
  if (prefersReducedMotion()) return gsap.set(element, { autoAlpha: entering ? 1 : 0 });
  return gsap.to(element, {
    autoAlpha: entering ? 1 : 0,
    duration: seconds(entering ? '--prope-motion-duration-base' : '--prope-motion-duration-fast'),
    ease: cssToken('--prope-motion-ease-standard'),
  });
}

export function enterSurface(element: Element) {
  return animatePresence(element, 'surface', true);
}
