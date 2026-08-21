import { z } from 'zod';

import { apiRequest } from '@/lib/apiClient';
import {
  probeStartSchema,
  readinessCardSchema,
  ruleSchema,
  type ProbeStart,
  type ReadinessCard,
  type ReadinessRule,
  type UsageProfileAxis,
} from '@/features/prompt-lifecycle/readinessTypes';

/**
 * INT-038..INT-042. The readiness card, the probe, and the rule catalogue.
 *
 * **No mock arm.** `insightsApi.ts`'s rule, for its reason: a card that invents a
 * finding is worse than a card that is down, because somebody will make a release
 * decision on it. A stack that cannot answer fails at the fetch and `QueryState`
 * renders that honestly.
 *
 * **`getReadinessCard` is a GET that writes**, and the call site should know it.
 * Once a revision leaves `Draft`, the first read freezes the reviewer's copy —
 * ADR-0067's SR-1, because release-control is a forbidden dependency in both
 * directions and a submit hook would be an edge. Reading twice is safe and
 * returns the same bytes; the write is idempotent under a unique constraint.
 */

export type ReadinessTrigger = 'import' | 'edit' | 'submit';

export async function getReadinessCard(
  promptId: string,
  versionId: string,
  trigger: ReadinessTrigger = 'edit',
): Promise<ReadinessCard> {
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/revisions/${encodeURIComponent(versionId)}` +
      `/readiness?trigger=${trigger}`,
    { schema: readinessCardSchema },
  );
}

/**
 * Start a probe. **This spends the workspace's provider credit.**
 *
 * It takes no case count and no model override, and the absence is deliberate
 * (A-164): a case count a caller can raise is a spend a caller can raise, and a
 * fixed shipped set is what makes the number comparable between two prompts at
 * all. Refuses with `spend_ceiling_reached` before dispatching anything.
 */
export async function startProbe(promptId: string, versionId: string): Promise<ProbeStart> {
  return apiRequest(
    `/api/v1/prompts/${encodeURIComponent(promptId)}/revisions/${encodeURIComponent(versionId)}/probe`,
    { method: 'POST', schema: probeStartSchema },
  );
}

/**
 * Dismiss a finding, with a reason. Per (prompt, rule) and carried across
 * revisions, so the panel does not re-nag on every save.
 *
 * The reason is required by the server and by the database, and it is not
 * ceremony: the dismissal rate per rule decides which rules get retired
 * (OQ-157), and a rate with no reasons attached cannot tell *the rule is wrong*
 * from *the profile filter is wrong*, which are opposite fixes.
 */
export async function dismissFinding(
  promptId: string,
  ruleId: string,
  reason: string,
): Promise<void> {
  await apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}/readiness/dismissals`, {
    method: 'POST',
    body: JSON.stringify({ rule_id: ruleId, reason }),
  });
}

/**
 * The closed rule catalogue.
 *
 * Fetched so a legend can render every code the card might return, and so a
 * missing translation shows up as a missing key rather than as a blank row. CI
 * asserts the `vi` catalogue is total over exactly this set.
 */
export async function listReadinessRules(): Promise<ReadinessRule[]> {
  return apiRequest('/api/v1/readiness/rules', { schema: z.array(ruleSchema) });
}

/**
 * Declare one Usage Profile axis. `PATCH /api/v1/prompts/{id}`, not a route of
 * this module's own.
 *
 * **The write belongs to prompt-registry because the column does.** These four
 * axes live on `registry.prompt_property`; readiness reads them and owns none of
 * them, and a second endpoint would be a second permission decision — this one
 * declares `prompt.edit`, which is the permission that already governs changing
 * what a prompt is.
 *
 * One axis per call, deliberately. A person answers these questions one at a
 * time and a partial answer is a real state: three declared and one still
 * `undeclared` keeps the worst-case badge on the fourth, which is exactly what
 * should happen.
 */
export async function declareUsageProfileAxis(
  promptId: string,
  axis: UsageProfileAxis,
  value: string,
): Promise<void> {
  await apiRequest(`/api/v1/prompts/${encodeURIComponent(promptId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ [axis]: value }),
  });
}
