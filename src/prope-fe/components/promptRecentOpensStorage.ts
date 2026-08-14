const STORAGE_KEY = 'prompt_recent_opens';
const MAX_RECENT = 5;

export interface RecentPrompt {
  id: string;
  title: string;
  visitedAt: string;
}

function readRecentPrompts(): RecentPrompt[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown[];
    if (!Array.isArray(parsed)) return [];
    return (parsed as unknown[])
      .filter(
        (raw): raw is RecentPrompt =>
          typeof raw === 'object' &&
          raw !== null &&
          'id' in raw &&
          'title' in raw &&
          typeof (raw as Record<string, unknown>).id === 'string' &&
          typeof (raw as Record<string, unknown>).title === 'string',
      );
  } catch {
    return [];
  }
}

export function trackPromptOpen(id: string, title: string): void {
  const existing = readRecentPrompts().filter((p) => p.id !== id);
  const updated = [{ id, title, visitedAt: new Date().toISOString() }, ...existing].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // localStorage unavailable — ignore
  }
}

export function readRecentPromptsList(): RecentPrompt[] {
  return readRecentPrompts();
}