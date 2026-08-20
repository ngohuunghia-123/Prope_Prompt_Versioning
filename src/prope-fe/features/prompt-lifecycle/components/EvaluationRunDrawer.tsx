import { useTranslation } from 'react-i18next';
import { Drawer } from '@/components/ui/Drawer';
import { EvalRunResults } from '@/features/prompt-lifecycle/components/EvalRunResults';
import { useEvalRunReports } from '@/features/prompt-lifecycle/useEvalRunReports';
import type { EvalRunSummary } from '@/features/prompt-lifecycle/insightsTypes';

export function EvaluationRunDrawer({ run, onClose }: { run?: EvalRunSummary; onClose: () => void }) {
  const { t } = useTranslation();
  const handles = run ? [{ run_id: run.run_id, suite_id: run.suite_id, suite_name: run.suite_name ?? run.dataset_name ?? run.suite_id, suite_version: run.suite_version ?? 1, role: run.role }] : [];
  const { reports } = useEvalRunReports(handles);
  return (
    <Drawer open={Boolean(run)} onClose={onClose} side="right" size="full" title={t('lifecycle.insights.evaluation.runDetail')}>
      <div className="h-full overflow-y-auto p-4 sm:p-6">{run ? <EvalRunResults reports={reports} /> : null}</div>
    </Drawer>
  );
}
