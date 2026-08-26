# Chat message content sizing

## Understanding summary

- PropAI responses may contain an approval card whose fields and actions are taller than plain text.
- The message currently shrinks inside the chat column and clips its overflow.
- A response must hug its complete content vertically.
- The thread, not an individual message, owns vertical scrolling.
- Long text must continue wrapping within the navigation panel width.
- The composer remains fixed at the bottom of the panel.

## Assumptions

- Message history can grow without a fixed per-message height.
- Existing width tokens and typography remain unchanged.
- Approval content remains keyboard reachable and is never hidden behind clipping.
- No API, persistence, or message schema changes are required.

## Final design

Keep the thread as the single `overflow-y-auto` region. Make each agent message a non-shrinking,
content-sized flex child and remove vertical clipping from its outer article and response surface.
The inner content continues using `min-w-0`, word breaking, and the existing maximum-width token,
so hug-content height does not introduce horizontal overflow.

```text
chat thread (scrolls)
└─ message (shrink-0, h-fit)
   └─ response surface (h-fit)
      ├─ response text
      ├─ approval card
      └─ message actions
```

## Decision log

1. Chose message-level intrinsic height over adding a nested scrollbar to the approval card, because
   one conversation should have one vertical scroll surface.
2. Removed clipping from the response surface instead of increasing a fixed height, because approval
   card content varies by tool and locale.
3. Preserved the existing width and visual tokens; this is a layout correction, not a chat redesign.

## Verification

- TypeScript, lint, and production build pass.
- Approval cards render their full fields and action buttons.
- The thread scrolls to the bottom after a tall message arrives.
- Long summaries and preview values wrap without horizontal overflow.
