import { useEffect, useMemo, useState } from 'react';
import type { EvalDatasetResult } from '@/features/prompt-lifecycle/types';

export function useEvalWorkspaceSelection(datasets: EvalDatasetResult[]) {
  const [datasetId, setDatasetId] = useState('');
  const [testId, setTestId] = useState('');
  const dataset = useMemo(() => datasets.find((item) => item.id === datasetId) ?? datasets[0], [datasetId, datasets]);
  const test = useMemo(() => dataset?.tests.find((item) => item.id === testId) ?? dataset?.tests[0], [dataset, testId]);

  useEffect(() => {
    if (!datasetId && datasets[0]) setDatasetId(datasets[0].id);
  }, [datasetId, datasets]);

  useEffect(() => {
    if (dataset && !dataset.tests.some((item) => item.id === testId)) setTestId(dataset.tests[0]?.id ?? '');
  }, [dataset, testId]);

  return { dataset, datasetId: dataset?.id ?? datasetId, setDatasetId, test, testId: test?.id ?? testId, setTestId };
}
