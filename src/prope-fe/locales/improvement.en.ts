/**
 * ADR-0068's detector catalogue, in English.
 *
 * **`vi` is the interface language and this is the development mirror**
 * (ADR-0053). CI asserts the `vi` catalogue is total over `DetectorId` and
 * `RemedyFamily`; this one exists so a developer reading a failing test can see
 * what a key means without translating it back. The two are kept structurally
 * identical on purpose — a key present here and missing there is exactly the
 * drift the check catches.
 */
export const improvementEn = {
  inbox: {
    title: 'Post-publish watch',
    subtitle: 'Is the released prompt still doing the job it was approved to do?',
    empty: 'Nothing found. The last sweep saw every released prompt behaving normally.',
    emptyHint: 'This is the healthy state, not missing data.',
    warnings: '{{count}} warnings',
    advice: '{{count}} suggestions',
    occurrences: 'Seen {{count}} times',
    firstSeen: 'First: {{when}}',
    lastSeen: 'Latest: {{when}}',
    openPrompt: 'Open prompt',
    dismiss: 'Dismiss',
    dismissReason: 'Reason for dismissing',
    dismissReasonPlaceholder: 'Why is this not worth acting on?',
    dismissReasonRequired:
      'A reason is required — the dismissal rate is what retires a detector from the set.',
  },
  severity: {
    warning: 'Warning',
    advice: 'Suggestion',
  },
  proposal: {
    title: 'Proposal',
    expiresAt: 'Expires {{when}}',
    accept: 'Open the editor with the proposed body',
    acceptHint: 'Nothing has changed yet. The edit is written only when you save a revision.',
    dismiss: 'Not applicable',
    gateTitle: "Result of running this prompt's own suite",
    gateSummary: '{{candidate}}/{{total}} cases pass, previously {{baseline}}/{{total}}',
    gateHint:
      'A proposal only appears after it has run against the suite without breaking a passing case.',
    gateLimit: 'A suite is only as strong as what it measures. This is a floor, not a proof.',
    caseBaseline: 'Before',
    caseCandidate: 'After',
    noBody: 'This proposal carries no body change.',
  },
  kind: {
    note: 'Information',
    case: 'Proposed cases',
    edit: 'Proposed edit',
  },
  family: {
    tighten_refusal_block: {
      title: 'Tighten the refusal path',
      body: 'Adds a constraints block stating when to refuse and never to reveal the system instructions.',
    },
    add_length_rule: {
      title: 'Add a length rule',
      body: 'Adds an output-format block naming a maximum length, instead of answers being cut off.',
    },
    add_brevity_clause: {
      title: 'Add a brevity clause',
      body: 'Adds a constraint to answer concisely, to reduce the rising output token share.',
    },
  },
  schedule: {
    title: 'Scheduled guardrail re-check',
    description:
      'Re-runs the adversarial case sets against the released revision, to catch a guardrail that became bypassable when the provider changed the model.',
    enabled: 'Enabled',
    cadence: 'Cadence (days)',
    estimate: 'Estimated about {{amount}} per week',
    estimateHint: 'Computed from the price row in force and the case count, not from measured spend.',
    scopeAll: 'Applies to every released prompt',
    lastRun: 'Last run: {{when}}',
    never: 'Never run',
  },
  detector: {
    truncation_rising: {
      title: 'More answers are being cut off',
      body: '{{share}} of calls truncated, previously {{prior_share}}. The discarded tokens are still billed.',
      action: 'State a maximum length in the prompt, or raise max_tokens at the call site',
    },
    fallback_rising: {
      title: 'Users are getting the fallback answer',
      body: '{{share}} of calls fell back, previously {{prior_share}}. The released revision is failing upstream.',
      action: 'Check the provider configuration and the released revision',
    },
    caller_error_clustering: {
      title: 'The integration is sending bad requests',
      body: '{{share}} of calls were refused as caller errors, previously {{prior_share}}. Usually a missing variable or a dropped messages shape.',
      action: "Compare the integration against the released revision's variable list",
    },
    output_ratio_drift: {
      title: 'The model got chattier',
      body: 'Output-to-input token ratio is {{ratio}}, previously {{prior_ratio}}. Output costs several times input.',
      action: 'Add a brevity requirement',
    },
    usage_unknown_appearing: {
      title: 'The provider stopped reporting usage',
      body: '{{count}} calls carry no token figures. Every cost number after this is MISSING, not zero.',
      action: "Check the provider's API version",
    },
    cost_unpriced_appearing: {
      title: 'A model is serving with no price row',
      body: '{{count}} calls ran on an upstream model with no matching price row.',
      action: 'Add a price row for the model that is serving',
    },
    latency_tail_shift: {
      title: 'The latency tail moved',
      body: 'P95 is {{p95_ms}}ms, previously {{prior_p95_ms}}ms. The tail is what users actually experience.',
      action: "Review the released revision's model and parameters",
    },
    pinned_share_rising: {
      title: 'Consumers are pinning away from the release',
      body: '{{share}} of calls pin a specific version instead of the released one, previously {{prior_share}}.',
      action: 'Ask the integrator why they are not taking the approved revision',
    },
    chain_depth_rising: {
      title: 'Retry or loop behaviour at the call site',
      body: '{{share}} of calls sit inside a chain, previously {{prior_share}}. Usually a loop or a retry in the caller.',
      action: "Review the caller's retry logic",
    },
    released_but_unused: {
      title: 'A governed prompt nobody calls',
      body: 'Released {{days_since_release}} days ago with no calls in the window.',
      action: 'Consider retiring it, to reduce what has to be reviewed',
    },
    profile_drift: {
      title: 'The declared purpose changed after release',
      body: 'The current usage profile differs from the copy stamped at approval. What is serving was approved under a different exposure.',
      action: 'Create a revision so it is re-approved under the current purpose',
    },
    probe_leak_appeared: {
      title: 'A guardrail became bypassable',
      body: '{{leaked}} of {{cases}} cases leaked, previously {{prior_leaked}}. Nothing errored — this is only visible by measuring again.',
      action: 'Tighten the refusal path in the prompt',
    },
  },
} as const;
