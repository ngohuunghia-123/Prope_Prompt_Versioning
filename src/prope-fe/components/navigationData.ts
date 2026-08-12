import {
  CalendarCheck,
  CheckCircle,
  CirclesThreePlus,
  CursorClick,
  FileText,
  Folder,
  GitCommit,
  Palette,
  PencilSimple,
  ShieldCheck,
  Tag,
  PersonArmsSpread,
  UsersThree,
} from '@phosphor-icons/react';
import type { NavigationSearchResult, NavigationUpdate } from '@/components/navigationTypes';

export const navigationSearchResults: NavigationSearchResult[] = [
  { id: 'customer-support', icon: FileText, searchTerms: 'customer support agent linh owner production', titleKey: 'customerSupport', descriptionKey: 'customerSupportDescription', kindKey: 'prompt', href: '#prompt/customer-support' },
  { id: 'claim-screening', icon: ShieldCheck, searchTerms: 'claim screening quang risk review', titleKey: 'claimScreening', descriptionKey: 'claimScreeningDescription', kindKey: 'prompt', href: '#prompt/claim-screening' },
  { id: 'evaluation', icon: Folder, searchTerms: 'evaluation datasets regression tests folder', titleKey: 'evaluationDatasets', descriptionKey: 'evaluationDatasetsDescription', kindKey: 'folder', href: '#folder/evaluation' },
  { id: 'production', icon: Tag, searchTerms: 'production trusted approved tag', titleKey: 'production', descriptionKey: 'productionDescription', kindKey: 'tag', href: '#tag/production' },
];

export const navigationUpdateGroups: Array<{ labelKey: string; items: NavigationUpdate[] }> = [
  { labelKey: 'today', items: [
    { id: 'design-vault', icon: PencilSimple, date: '2026-08-09T15:30:00', titleKey: 'designVaultTitle', bodyKey: 'designVaultBody' },
    { id: 'prototype', icon: CirclesThreePlus, date: '2026-08-09T16:00:00', titleKey: 'prototypeTitle', bodyKey: 'prototypeBody' },
    { id: 'palette', icon: Palette, date: '2026-08-09T16:45:00', titleKey: 'paletteTitle', bodyKey: 'paletteBody' },
  ] },
  { labelKey: 'yesterday', items: [
    { id: 'components', icon: CheckCircle, date: '2026-08-08T10:15:00', titleKey: 'componentsTitle', bodyKey: 'componentsBody' },
    { id: 'feedback', icon: GitCommit, date: '2026-08-08T11:00:00', titleKey: 'feedbackTitle', bodyKey: 'feedbackBody' },
    { id: 'tests', icon: UsersThree, date: '2026-08-08T12:30:00', titleKey: 'testsTitle', bodyKey: 'testsBody' },
  ] },
  { labelKey: 'twoDaysAgo', items: [
    { id: 'interactions', icon: CursorClick, date: '2026-08-07T09:00:00', titleKey: 'interactionsTitle', bodyKey: 'interactionsBody' },
    { id: 'accessibility', icon: PersonArmsSpread, date: '2026-08-07T10:15:00', titleKey: 'accessibilityTitle', bodyKey: 'accessibilityBody' },
    { id: 'review', icon: CalendarCheck, date: '2026-08-07T11:45:00', titleKey: 'reviewTitle', bodyKey: 'reviewBody' },
  ] },
];
