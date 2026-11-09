const assetBase = document.querySelector('meta[name="prope-assets"]')?.getAttribute('content') ?? '';
export const FLOATING_AGENT_ASSETS = {
  avatar: `${assetBase}/assets/mascot/avatar.webp`,
  empty: `${assetBase}/assets/mascot/empty-state.webp`,
  idle: `${assetBase}/assets/mascot/idle.webp`,
  active: `${assetBase}/assets/mascot/mascot-animate.gif`,
} as const;
