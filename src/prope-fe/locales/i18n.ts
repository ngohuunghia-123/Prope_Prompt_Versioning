import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from '@/locales/en';
import { vi } from '@/locales/vi';

void i18n.use(initReactI18next).init({
  resources: { en, vi },
  lng: 'vi',
  fallbackLng: 'vi',
  interpolation: { escapeValue: false },
});

export { i18n };
