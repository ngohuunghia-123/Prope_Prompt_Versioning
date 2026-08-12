import { gsap } from 'gsap';

function cssToken(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function seconds(name: string) {
  return Number.parseFloat(cssToken(name)) / 1000;
}

export function enterSurface(element: Element) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return gsap.set(element, { autoAlpha: 1, y: 0 });
  }
  return gsap.fromTo(
    element,
    { autoAlpha: 0, y: Number.parseFloat(cssToken('--prope-motion-distance-enter')) },
    { autoAlpha: 1, y: 0, duration: seconds('--prope-motion-duration-base'), ease: cssToken('--prope-motion-ease-standard') },
  );
}
