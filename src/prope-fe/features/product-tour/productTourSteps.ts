export interface ProductTourStep {
  id: string;
  targetId: string;
  pathname: string;
  hash: '#home' | '#search' | '#chat';
  navigationOpen: boolean;
  expandTasks?: boolean;
  titleKey: string;
  bodyKey: string;
}

export const PRODUCT_TOUR_STEPS: readonly ProductTourStep[] = [
  {
    id: 'navigation', targetId: 'navigation-modes', pathname: '/app/prompts', hash: '#home', navigationOpen: true,
    titleKey: 'lifecycle.productTour.steps.navigation.title', bodyKey: 'lifecycle.productTour.steps.navigation.body',
  },
  {
    id: 'home', targetId: 'workspace-home', pathname: '/app/home', hash: '#home', navigationOpen: false,
    titleKey: 'lifecycle.productTour.steps.home.title', bodyKey: 'lifecycle.productTour.steps.home.body',
  },
  {
    id: 'registry', targetId: 'prompt-registry', pathname: '/app/prompts', hash: '#home', navigationOpen: false,
    titleKey: 'lifecycle.productTour.steps.registry.title', bodyKey: 'lifecycle.productTour.steps.registry.body',
  },
  {
    id: 'search', targetId: 'search', pathname: '/app/prompts', hash: '#search', navigationOpen: true,
    titleKey: 'lifecycle.productTour.steps.search.title', bodyKey: 'lifecycle.productTour.steps.search.body',
  },
  {
    id: 'chat', targetId: 'chat', pathname: '/app/prompts', hash: '#chat', navigationOpen: true,
    titleKey: 'lifecycle.productTour.steps.chat.title', bodyKey: 'lifecycle.productTour.steps.chat.body',
  },
  {
    id: 'tools', targetId: 'tools', pathname: '/app/prompts', hash: '#home', navigationOpen: true,
    titleKey: 'lifecycle.productTour.steps.tools.title', bodyKey: 'lifecycle.productTour.steps.tools.body',
  },
  {
    id: 'import', targetId: 'import', pathname: '/app/imports/new', hash: '#home', navigationOpen: false,
    titleKey: 'lifecycle.productTour.steps.import.title', bodyKey: 'lifecycle.productTour.steps.import.body',
  },
  {
    id: 'tasks', targetId: 'background-tasks', pathname: '/app/prompts', hash: '#home', navigationOpen: false, expandTasks: true,
    titleKey: 'lifecycle.productTour.steps.tasks.title', bodyKey: 'lifecycle.productTour.steps.tasks.body',
  },
];
