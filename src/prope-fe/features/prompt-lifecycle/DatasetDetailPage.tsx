import { useParams } from 'react-router-dom';
import { DatasetDetailView } from '@/features/prompt-lifecycle/DatasetDetailView';

export function DatasetDetailPage() {
  const { datasetId } = useParams();
  return <DatasetDetailView datasetId={datasetId} />;
}
