import type { Icon } from '@phosphor-icons/react';

export type NavigationMode = 'home' | 'chat' | 'notifications' | 'search';

export interface NavigationMessage {
  id: number;
  role: 'user' | 'agent';
  text: string;
}

export interface NavigationSearchResult {
  id: string;
  icon: Icon;
  searchTerms: string;
  titleKey: string;
  descriptionKey: string;
  kindKey: string;
  href: string;
}

export interface NavigationUpdate {
  id: string;
  icon: Icon;
  date: string;
  titleKey: string;
  bodyKey: string;
}
