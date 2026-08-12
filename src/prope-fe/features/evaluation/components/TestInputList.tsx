import { CheckCircle, Flask } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '@/components/StatusBadge';
import type { TestInput } from '@/features/evaluation/types';

interface TestInputListProps { inputs: TestInput[]; }

export function TestInputList({ inputs }: TestInputListProps) {
  const { t } = useTranslation();
  if (inputs.length === 0) return <div className="grid min-h-40 place-items-center rounded-modal border border-dashed border-border bg-canvas p-5 text-center"><div><Flask aria-hidden className="mx-auto size-8 text-muted" /><h3 className="mt-3 text-heading-3 font-semibold text-ink">{t('evaluation.inputs.emptyTitle')}</h3><p className="mt-1 text-body text-muted">{t('evaluation.inputs.emptyBody')}</p></div></div>;
  return (
    <ul className="space-y-3">
      {inputs.map((input) => <li key={input.id} className="rounded-modal border border-border bg-surface p-4 shadow-panel sm:p-5"><div className="flex items-start gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-full bg-success text-success-text"><CheckCircle aria-hidden className="size-5" weight="fill" /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-body-large font-semibold text-ink">{input.name}</h3><StatusBadge tone="active">{t('evaluation.inputs.reusable')}</StatusBadge></div><p className="mt-2 text-body text-muted">{input.content}</p></div></div></li>)}
    </ul>
  );
}
