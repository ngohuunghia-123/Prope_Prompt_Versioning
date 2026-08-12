import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export interface ComponentShowcaseProps {
  name: string;
  source: string;
  kind: 'primitive' | 'composed';
  children: ReactNode;
}

export function ComponentShowcase({ name, source, kind, children }: ComponentShowcaseProps) {
  const { t } = useTranslation();
  return (
    <article className="overflow-hidden rounded-modal border border-border bg-surface shadow-panel">
      <header className="border-b border-border bg-subtle px-5 py-4 sm:px-6">
        <h3 className="text-heading-3 font-semibold text-ink">{name}</h3>
        <dl className="mt-3 grid gap-2 text-caption sm:grid-cols-[auto_1fr] sm:gap-x-4">
          <dt className="font-semibold text-muted">{t('componentLab.metadata.file')}</dt>
          <dd><code className="break-all text-link">{source}</code></dd>
          <dt className="font-semibold text-muted">{t('componentLab.metadata.kind')}</dt>
          <dd className="text-ink">{t(`componentLab.metadata.${kind}`)}</dd>
        </dl>
      </header>
      <div className="flex min-h-36 items-center p-5 sm:p-6">{children}</div>
    </article>
  );
}
