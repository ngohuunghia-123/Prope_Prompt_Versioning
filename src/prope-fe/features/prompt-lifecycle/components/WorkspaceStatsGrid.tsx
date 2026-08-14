import { TrendUp, CurrencyDollar, ChartLine, Stack } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/components/Card';
import type { WorkspaceStats } from '@/features/prompt-lifecycle/types';

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  variant?: 'default' | 'success' | 'warning' | 'info';
}

function StatCard({ icon, label, value, variant = 'default' }: StatCardProps) {
  const bgClass = {
    default: 'bg-surface',
    success: 'bg-success/10',
    warning: 'bg-warning/10',
    info: 'bg-info/10',
  }[variant];

  const iconColorClass = {
    default: 'text-secondary',
    success: 'text-success-strong',
    warning: 'text-warning-strong',
    info: 'text-info-strong',
  }[variant];

  const valueColorClass = {
    default: 'text-ink',
    success: 'text-success-strong',
    warning: 'text-warning-strong',
    info: 'text-info-strong',
  }[variant];

  return (
    <Card className={`flex min-h-32 flex-col gap-3 ${bgClass}`}>
      <div className="flex items-center justify-between">
        <span className="text-caption text-muted">{label}</span>
        <div className={`flex size-9 items-center justify-center rounded-lg bg-subtle/50 ${iconColorClass}`}>
          {icon}
        </div>
      </div>
      <span className={`font-display text-heading-1 font-semibold ${valueColorClass}`}>
        {value}
      </span>
    </Card>
  );
}

interface WorkspaceStatsGridProps {
  stats: WorkspaceStats;
}

export function WorkspaceStatsGrid({ stats }: WorkspaceStatsGridProps) {
  const { t } = useTranslation();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('en-US').format(value);
  };

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={<Stack aria-hidden className="size-5" weight="duotone" />}
        label={t('lifecycle.workspace.stats.totalPrompts')}
        value={stats.totalPrompts}
        variant="default"
      />
      <StatCard
        icon={<TrendUp aria-hidden className="size-5" weight="duotone" />}
        label={t('lifecycle.workspace.stats.qualityPercent')}
        value={formatPercent(stats.qualityPercent)}
        variant="success"
      />
      <StatCard
        icon={<CurrencyDollar aria-hidden className="size-5" weight="duotone" />}
        label={t('lifecycle.workspace.stats.totalCost')}
        value={formatCurrency(stats.totalCost7Days)}
        variant="info"
      />
      <StatCard
        icon={<ChartLine aria-hidden className="size-5" weight="duotone" />}
        label={t('lifecycle.workspace.stats.totalRequests')}
        value={formatNumber(stats.totalRequests7Days)}
        variant="warning"
      />
    </div>
  );
}
