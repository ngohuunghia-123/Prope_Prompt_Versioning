import { useEffect, useState } from 'react';
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

  useEffect(() => {
    const intervalId = window.setInterval(() => setActiveIndex((currentIndex) => (currentIndex + 1) % slides.length), 3000);
    return () => window.clearInterval(intervalId);
  }, []);

  return (
    <section className="relative hidden min-h-dvh overflow-hidden bg-hero text-inverse lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-1/2" aria-roledescription="carousel" aria-label={t('auth.carousel.label')}>
      {slides.map((slide, index) => (
        <img
          key={slide.key}
          src={slide.image}
          alt=""
          className={cn('absolute inset-0 size-full object-cover transition-opacity duration-(--prope-motion-duration-slow)', index === activeIndex ? 'opacity-100' : 'opacity-0')}
        />
      ))}
      <div className="absolute inset-x-0 bottom-0 h-auth-carousel-mask bg-gradient-to-t from-hero/80 to-transparent" />
      <div className="relative z-10 flex w-full items-end justify-center px-12 pb-8 text-center">
        <div className="max-w-auth">
          <h1 className="font-display text-auth-visual font-semibold">{t(`auth.carousel.slides.${activeSlide.key}.title`)}</h1>
          <p className="mt-4 text-body-large text-landing-muted">{t(`auth.carousel.slides.${activeSlide.key}.description`)}</p>
        </div>
      </div>
    </section>
  );
}
