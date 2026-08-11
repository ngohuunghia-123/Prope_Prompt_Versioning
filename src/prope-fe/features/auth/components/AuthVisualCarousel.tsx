import { CaretLeft, CaretRight } from '@phosphor-icons/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

const slides = [
  { key: 'ownership', image: '/auth-carousel/ownership.webp' },
  { key: 'provenance', image: '/auth-carousel/provenance.webp' },
  { key: 'release', image: '/auth-carousel/release.webp' },
] as const;

export function AuthVisualCarousel() {
  const { t } = useTranslation();
  const [activeIndex, setActiveIndex] = useState(0);
  const activeSlide = slides[activeIndex] ?? slides[0];
  const selectRelative = (offset: number) => setActiveIndex((activeIndex + offset + slides.length) % slides.length);

  return (
    <section className="relative hidden min-h-dvh overflow-hidden bg-hero text-inverse lg:flex lg:items-center lg:justify-center" aria-roledescription="carousel" aria-label={t('auth.carousel.label')}>
      {slides.map((slide, index) => (
        <img
          key={slide.key}
          src={slide.image}
          alt=""
          className={cn('absolute inset-0 size-full object-cover transition-opacity duration-(--prope-motion-duration-slow)', index === activeIndex ? 'opacity-70' : 'opacity-0')}
        />
      ))}
      <div className="absolute inset-0 bg-gradient-to-b from-hero/30 via-hero/45 to-hero/90" />
      <div className="relative z-10 mx-auto flex max-w-copy flex-col items-center px-12 text-center" aria-live="polite">
        <p className="text-overline font-semibold uppercase tracking-button text-primary">{t(`auth.carousel.slides.${activeSlide.key}.eyebrow`)}</p>
        <h1 className="mt-4 max-w-auth font-display text-auth-visual font-semibold">{t(`auth.carousel.slides.${activeSlide.key}.title`)}</h1>
        <p className="mt-4 max-w-auth text-body-large text-landing-muted">{t(`auth.carousel.slides.${activeSlide.key}.description`)}</p>
      </div>
      <div className="absolute inset-x-0 bottom-10 z-10 flex items-center justify-center gap-5">
        <button type="button" className="cursor-pointer rounded-full p-2 text-landing-muted focus-visible:outline-2 focus-visible:outline-focus" aria-label={t('auth.carousel.previous')} onClick={() => selectRelative(-1)}><CaretLeft aria-hidden className="size-5" /></button>
        <div className="flex gap-2" aria-hidden>
          {slides.map((slide, index) => <span key={slide.key} className={cn('size-2 rounded-full bg-landing-muted transition-transform', index === activeIndex && 'scale-125 bg-primary')} />)}
        </div>
        <button type="button" className="cursor-pointer rounded-full p-2 text-landing-muted focus-visible:outline-2 focus-visible:outline-focus" aria-label={t('auth.carousel.next')} onClick={() => selectRelative(1)}><CaretRight aria-hidden className="size-5" /></button>
      </div>
    </section>
  );
}
