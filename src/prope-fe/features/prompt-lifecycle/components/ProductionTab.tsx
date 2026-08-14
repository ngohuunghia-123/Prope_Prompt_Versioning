import { useQuery } from '@tanstack/react-query';
import { ProductionMetrics } from '@/features/prompt-lifecycle/components/ProductionMetrics';
import { ProductionProductTable } from '@/features/prompt-lifecycle/components/ProductionProductTable';
import { QueryState } from '@/features/prompt-lifecycle/components/QueryState';
import { productionOverviewOptions } from '@/features/prompt-lifecycle/queries';

interface ProductionTabProps {
  promptId: string;
}

export function ProductionTab({ promptId }: ProductionTabProps) {
  const query = useQuery(productionOverviewOptions(promptId));

  if (query.isPending) return <QueryState state="loading" />;
  if (query.isError) return <QueryState state="error" onRetry={() => void query.refetch()} />;
  if (query.data.products.length === 0) return <QueryState state="empty" />;

  return (
    <div className="grid gap-6">
      <ProductionMetrics overview={query.data} />
      <ProductionProductTable products={query.data.products} />
    </div>
  );
}
