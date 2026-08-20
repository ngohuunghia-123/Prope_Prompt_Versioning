/**
 * ADR-0067's rule catalogue, in English.
 *
 * **`vi` is the interface language and this is the development mirror**
 * (ADR-0053). CI asserts the `vi` catalogue is total over the rule set; this one
 * exists so a developer reading a failing test can see what a key means without
 * translating it back. The two are kept structurally identical on purpose — a
 * key present here and missing there is exactly the drift the check catches.
 */
export const readinessEn = {
  card: {
    title: 'Readiness',
    empty: 'Nothing found. This prompt is ready for the job it declares.',
    warnings: '{{count}} warnings',
    advice: '{{count}} suggestions',
    dismissed: '{{count}} dismissed',
    frozen: 'Frozen copy for the reviewer',
    frozenHint:
      'This is the record as it stood at submit. It does not change when the rule catalogue is updated.',
    live: 'Live against the current draft',
    catalogueVersion: 'Rule catalogue v{{version}}',
    laneBUnavailable: 'The model-assisted pass could not run. Everything else is complete.',
    showDismissed: 'Show dismissed',
    hideDismissed: 'Hide dismissed',
    dismiss: 'Dismiss',
    dismissReason: 'Reason for dismissing',
    dismissReasonPlaceholder: 'Why does this not apply to this prompt?',
    dismissReasonRequired:
      'A reason is required — the dismissal rate is what retires a rule from the catalogue.',
    dismissedBecause: 'Dismissed: {{reason}}',
    viewProposedEdit: 'View proposed edit',
    evidenceLabel: 'Evidence',
  },

  lane: {
    static: 'Static check',
    probe: 'Measured',
    drafted: 'Model-suggested',
  },

  severity: {
    warning: 'Warning',
    advice: 'Suggestion',
  },

  admitted: {
    always: 'Applies to every prompt',
    untrusted_input_present: 'Because this prompt takes untrusted content',
    all_three_legs: 'Because this prompt declares all three risk legs',
    can_act_or_absorbs_untrusted: 'Because this prompt can act, or takes outside content',
  },

  profile: {
    title: 'What is this prompt for?',
    description:
      'These four declarations decide what you get warned about. An internal-only prompt is never told it lacks a guardrail meant for public users.',
    undeclaredBadge: 'Undeclared — assuming worst case',
    undeclaredHint:
      'Nobody has declared how this prompt is used, so every rule is running at its strictest. One pass through these dropdowns settles it.',
    assumedAs: 'Assuming: {{value}}',
    axis: {
      audience: 'Who can reach this prompt?',
      untrusted_input: 'What untrusted content enters the context?',
      acts: 'What can the output cause to happen?',
      sensitivity: 'What class of data is in play?',
    },
    value: {
      undeclared: 'Undeclared',
      internal: 'Internal only',
      authenticated_user: 'Signed-in users',
      public: 'Public',
      none: 'None',
      user_text: 'User-supplied text',
      retrieved: 'Retrieved content (RAG)',
      third_party: 'Third-party sources',
      answers_only: 'Answers only',
      emits_tool_calls: 'Emits tool calls',
      irreversible: 'Irreversible actions',
      synthetic: 'Synthetic data',
      business: 'Business data',
      personal_data: 'Personal data',
    },
  },

  probe: {
    title: 'Measure against the adversarial set',
    description:
      'Runs the shipped attack cases against this exact revision. The result is a number, not an opinion.',
    start: 'Run the measurement',
    running: 'Running…',
    cost: "Spends the workspace's provider credit.",
    willRun: 'Will run: {{sets}}',
    lastRun: 'Last measurement',
    result: 'Refused {{refused}} of {{total}} cases',
    noSets: 'With the current declaration there is no set worth running.',
    refused: 'Refused',
    leaked: 'Got through',
    errors: 'Call errors',
    errorsHint: 'A call error is not a pass — those cases were not measured.',
    status: {
      running: 'Running',
      completed: 'Completed',
      partial: 'Partly completed',
      failed: 'Failed',
    },
    refusal: {
      spend_ceiling_reached: 'The workspace has reached its monthly spend ceiling.',
      no_applicable_sets: 'The current declaration needs no set.',
      revision_has_no_binding: 'This revision has no model bound to call.',
    },
  },

  rule: {
    interpolation_inside_instructions: {
      title: 'A variable is interpolated inside an instruction block',
      body: '{{count}} variables ({{variables}}) sit inside an instruction block, so text substituted into them is read as instruction rather than as data.',
      action: 'Move the variable into the context block',
    },
    placeholder_will_not_substitute: {
      title: 'Something looks like a variable and will not be substituted',
      body: 'Found {{count}} ({{found}}) that will reach the model verbatim, braces and all.',
      action: 'Rewrite as {{"{{variable_name}}"}}',
    },
    canonical_structure_weak: {
      title: 'Block structure is weak',
      body: 'Current block order: {{order}}. Context should come before the instruction that reads it.',
      action: 'Reorder the blocks',
    },
    no_eval_coverage: {
      title: 'This prompt has no eval suite',
      body: 'Submitting runs every suite — and a prompt with none passes trivially.',
      action: 'Create a first suite',
    },
    thin_eval_coverage: {
      title: 'The eval suite is thin',
      body: '{{cases}} cases, below {{threshold}}. Passing a thin suite says very little.',
      action: 'Add more cases',
    },
    lethal_trifecta: {
      title: 'All three risk legs are present',
      body: 'This prompt declares {{sensitivity}} data, takes {{untrusted_input}} content, and can {{acts}}. Together those three are enough for an injected instruction to become a real action.',
      action: 'Revisit the declaration, or remove one leg',
    },
    body_cost: {
      title: 'What the body alone costs',
      body: 'About {{approx_tokens}} tokens per call, before any input or output.',
      action: 'Trim the repetition',
    },
    profile_undeclared: {
      title: 'Usage is undeclared',
      body: '{{missing}} still unanswered. Every rule above ran at its strictest.',
      action: 'Declare how this prompt is used',
    },
    probe_injection_leaked: {
      title: 'Injection cases were not refused',
      body: '{{leaked}} of {{total}} injection cases were obeyed.',
      action: 'Add these cases to the suite',
    },
    probe_system_prompt_leaked: {
      title: 'The system prompt leaked',
      body: '{{leaked}} of {{total}} cases made the model print part of the system prompt back.',
      action: 'Add these cases to the suite',
    },
    probe_incomplete: {
      title: 'The measurement did not complete',
      body: '{{errors}} cases failed at the provider. Those cases were not measured.',
      action: 'Run it again',
    },
    contradictory_instructions: {
      title: 'Two instructions contradict each other',
      body: 'There are two instructions that cannot both be followed.',
      action: 'Review the instructions block',
    },
    redundant_body: {
      title: 'The body repeats itself',
      body: 'One instruction is stated more than once. The repetition costs tokens on every call.',
      action: 'Trim the repetition',
    },
    no_refusal_path: {
      title: 'There is no refusal path',
      body: 'The body says what to do and never what to do when it cannot. The failure mode of such a prompt is invention.',
      action: 'Add an instruction for what it cannot handle',
    },
  },
} as const;
