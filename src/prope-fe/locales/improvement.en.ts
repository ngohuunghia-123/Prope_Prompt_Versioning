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
    tabEmpty: 'No findings on this prompt.',
    tabEmptyHint: 'The last sweep looked at this prompt and found it behaving.',
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
    prefillTitle: 'The proposed body is in the form',
    prefillBody:
      'This is the proposal’s body and nothing is saved. Read it, change what you want, then save a revision — the released prompt is untouched until you do.',
    viewDiff: 'View the proposed body',
    hideDiff: 'Hide the proposed body',
    diffRequired:
      'An edit proposal shows its accept button only after you have seen the diff. The body could not be loaded.',
    rationaleTitle: 'Machine-proposed rationale (not evidence)',
    railsTitle: 'Rails check result',
    railsPassed: 'Cleared the rails after {{attempts}} draft attempt(s)',
    railsAttempt: 'Attempt {{attempt}}: refused {{code}}',
    improvementSummary: 'Failing cases on the target suite: {{before}} → {{after}}',
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
    llm_edit: {
      title: 'AI-drafted body edit',
      body: 'Prope’s model drafts the edit against the failing assertions, then it is bounded by the rails checks and this prompt’s own suite before it reaches you.',
    },
  },
  schedule: {
    title: 'Scheduled guardrail re-check',
    description:
      'Re-runs the adversarial case sets against the released revision, to catch a guardrail that became bypassable when the provider changed the model.',
    enabled: 'Enabled',
    cadence: 'Cadence (days)',
    cost: "Each cycle spends the workspace's provider credit, and repeats until you turn it off.",
    costHint:
      'No estimate is shown because none is measured. The spend ceiling is what actually stops it — a probe is refused when the ceiling is reached.',
    scopeAll: 'Applies to every released prompt',
    scopeSome: 'Selecting {{namespaces}} namespaces and {{prompts}} prompts',
    lastRun: 'Last run: {{when}}',
    never: 'Never run',
    save: 'Save schedule',
    saving: 'Saving…',
    saved: 'Schedule saved.',
    failed: 'The schedule was not saved. You may not have permission to manage spending.',
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
    eval_assertion_regex: {
      title: 'Answers violate the regex check',
      body: '{{failed}}/{{total}} answers match or miss the regex assertion in “{{suite_name}}”.',
      action: 'Propose a body edit for this failure group',
    },
    eval_assertion_forbidden_phrase: {
      title: 'Answers contain a forbidden phrase',
      body: '{{failed}}/{{total}} answers contain a forbidden phrase in “{{suite_name}}”.',
      action: 'Propose a body edit for this failure group',
    },
    eval_assertion_required_phrase: {
      title: 'Answers miss a required component',
      body: '{{failed}}/{{total}} answers miss a required component in “{{suite_name}}”.',
      action: 'Propose a body edit for this failure group',
    },
    eval_assertion_json_schema: {
      title: 'Output drifts off the schema',
      body: '{{failed}}/{{total}} answers break the schema in “{{suite_name}}”.',
      action: 'Propose a body edit for this failure group',
    },
    eval_assertion_max_length: {
      title: 'Answers exceed the length bound',
      body: '{{failed}}/{{total}} answers exceed the length bound in “{{suite_name}}”.',
      action: 'Propose a body edit for this failure group',
    },
    eval_assertion_max_latency: {
      title: 'Latency bound exceeded',
      body: '{{failed}}/{{total}} cases exceed the latency bound in “{{suite_name}}” — latency is rarely about the text.',
      action: 'Review the model and configuration before editing the prompt',
    },
    eval_assertion_max_cost: {
      title: 'Cost bound exceeded',
      body: '{{failed}}/{{total}} cases exceed the cost bound in “{{suite_name}}”.',
      action: 'Review the bound model and static context before editing the prompt',
    },
    eval_assertion_generic: {
      title: 'A case did not pass',
      body: '{{failed}}/{{total}} cases did not pass in “{{suite_name}}”.',
      action: 'Read the case detail, then propose a body edit',
    },
  },
} as const;
