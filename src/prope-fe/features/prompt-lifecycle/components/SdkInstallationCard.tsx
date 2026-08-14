import { Copy, Terminal } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import { Button } from '@/components/ui/Button';

interface SdkInstallationCardProps { promptId: string; }

export function SdkInstallationCard({ promptId }: SdkInstallationCardProps) {
  const { t } = useTranslation();
  const command = 'npm install @prope/sdk';
  const example = `import { PropeClient } from '@prope/sdk';

const client = new PropeClient({
  apiKey: 'your-api-key',
  promptId: '${promptId}'
});

const response = await client.complete({
  input: userQuery,
  variables: { customerTier: 'premium' }
});`;
  return (
    <Card title={t('lifecycle.overview.production.installation')}>
      <section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.production.installStep')}</h4><div className="mt-2 flex items-center gap-2 rounded-modal bg-ink p-3 text-inverse"><Terminal aria-hidden className="size-4" /><code className="flex-1 font-mono text-body">{command}</code><Button intent="ghost" size="icon" className="text-inverse hover:text-inverse" onClick={() => void navigator.clipboard.writeText(command)} aria-label={t('lifecycle.overview.production.copyInstall')}><Copy aria-hidden className="size-4" /></Button></div></section>
      <section><h4 className="text-caption font-medium text-muted">{t('lifecycle.overview.production.usageExample')}</h4><pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-modal bg-ink p-4 font-mono text-caption text-inverse">{example}</pre></section>
    </Card>
  );
}
