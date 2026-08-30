export function promptOverviewPath(modelName: string) {
  const [namespace = '', name = ''] = modelName.split('/');
  return `/app/prompts/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`;
}

export function promptOverviewUrl(modelName: string, search?: URLSearchParams | string) {
  const query = typeof search === 'string' ? search.replace(/^\?/, '') : search?.toString();
  return `${promptOverviewPath(modelName)}${query ? `?${query}` : ''}`;
}
