import { useTranslation } from 'react-i18next';

interface ColorToken {
  name: string;
  variable: `--prope-color-${string}`;
}

const colorTokens: ColorToken[] = [
  { name: 'canvas', variable: '--prope-color-bg-canvas' },
  { name: 'surface', variable: '--prope-color-bg-surface' },
  { name: 'subtle', variable: '--prope-color-bg-subtle' },
  { name: 'primary', variable: '--prope-color-bg-primary' },
  { name: 'primary-hover', variable: '--prope-color-bg-primary-hover' },
  { name: 'primary-loading', variable: '--prope-color-bg-primary-loading' },
  { name: 'secondary', variable: '--prope-color-bg-secondary' },
  { name: 'secondary-hover', variable: '--prope-color-bg-secondary-hover' },
  { name: 'success', variable: '--prope-color-bg-success' },
  { name: 'success-strong', variable: '--prope-color-bg-success-strong' },
  { name: 'danger', variable: '--prope-color-bg-danger' },
  { name: 'danger-strong', variable: '--prope-color-bg-danger-strong' },
  { name: 'warning', variable: '--prope-color-bg-warning' },
  { name: 'warning-strong', variable: '--prope-color-bg-warning-strong' },
  { name: 'info', variable: '--prope-color-bg-info' },
  { name: 'info-strong', variable: '--prope-color-bg-info-strong' },
  { name: 'disabled', variable: '--prope-color-bg-disabled' },
  { name: 'ink', variable: '--prope-color-text-primary' },
  { name: 'muted', variable: '--prope-color-text-secondary' },
  { name: 'inverse', variable: '--prope-color-text-inverse' },
  { name: 'link', variable: '--prope-color-text-link' },
  { name: 'danger-text', variable: '--prope-color-text-danger' },
  { name: 'success-text', variable: '--prope-color-text-success' },
  { name: 'warning-text', variable: '--prope-color-text-warning' },
  { name: 'disabled-text', variable: '--prope-color-text-disabled' },
  { name: 'border', variable: '--prope-color-border-default' },
  { name: 'border-strong', variable: '--prope-color-border-strong' },
  { name: 'focus', variable: '--prope-color-border-focus' },
  { name: 'border-disabled', variable: '--prope-color-border-disabled' },
  { name: 'border-success', variable: '--prope-color-border-success' },
  { name: 'tag-info', variable: '--prope-color-tag-info' },
  { name: 'tag-info-soft', variable: '--prope-color-tag-info-soft' },
  { name: 'hero', variable: '--prope-color-bg-hero' },
  { name: 'hero-soft', variable: '--prope-color-bg-hero-soft' },
  { name: 'accent-soft', variable: '--prope-color-bg-accent-soft' },
  { name: 'landing-muted', variable: '--prope-color-text-landing-muted' },
  { name: 'navigation-surface', variable: '--prope-color-navigation-surface' },
  { name: 'navigation-control', variable: '--prope-color-navigation-control' },
  { name: 'navigation-overline', variable: '--prope-color-navigation-overline' },
  { name: 'navigation-tab', variable: '--prope-color-navigation-tab' },
  { name: 'navigation-active', variable: '--prope-color-navigation-active' },
  { name: 'navigation-avatar', variable: '--prope-color-navigation-avatar' },
  { name: 'navigation-icon', variable: '--prope-color-navigation-icon' },
];

export function ColorTokensSection() {
  const { t } = useTranslation();

  return (
    <section className="space-y-5" aria-labelledby="component-lab-colors-title">
      <div className="max-w-copy space-y-2">
        <h2 id="component-lab-colors-title" className="text-heading-2 font-semibold text-ink">
          {t('componentLab.colors.title')}
        </h2>
        <p className="text-body text-muted">{t('componentLab.colors.description')}</p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {colorTokens.map((token) => (
          <li key={token.variable} className="overflow-hidden rounded-modal border border-border bg-surface">
            <div className="grid grid-cols-2">
              {(['light', 'dark'] as const).map((theme) => (
                <div key={theme} data-theme={theme} className="flex items-center gap-2 bg-canvas p-3 text-ink">
                  <span
                    aria-hidden
                    className="size-8 shrink-0 rounded-control border border-border"
                    style={{ backgroundColor: `var(${token.variable})` }}
                  />
                  <span className="text-caption font-semibold">{t(`componentLab.colors.${theme}`)}</span>
                </div>
              ))}
            </div>
            <div className="grid gap-1 border-t border-border px-3 py-2">
              <span className="text-body font-semibold text-ink">{token.name}</span>
              <code className="break-all text-caption text-muted">{token.variable}</code>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
