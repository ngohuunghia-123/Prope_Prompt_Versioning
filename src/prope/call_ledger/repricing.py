"""CL-05: a price row added after the fact fills only what was never priced.

ADR-0019: "Repricing fills only previously-unpriced rows. A row that already has
a cost is never recomputed — that is the rule that makes history stable." A cost
that a reviewer has already seen, approved and acted on is a fact about the
past; recomputing it silently would make an approval record disagree with itself
and would leave nothing behind to say when it changed.

**The whole guarantee is one predicate, and it is the status column.** The
selection below and the update below both restrict to rows whose ``cost_status``
holds the unpriced value. That predicate — and not the shape of the update, not
the ordering, not the caller's diligence — is what makes an already-priced row
unreachable from here.

**It must never be widened to a test on the cost column being absent.** The
three cost states are ``priced``, ``unpriced`` and ``not_applicable``, and the
third one has no cost either: it is a call whose provider returned no usage
object, so both token columns are NULL and there is nothing to multiply by a
price. A filter written against the cost column instead of the status column
would select those rows too, and would then price calls whose token counts
nobody ever reported. The status is the question being asked; the absent cost is
merely one of its consequences, and two different states share it.

**One cost function, not two.** ``resolve_price`` and ``compute_cost`` are
imported from ``pricing``, the module the writer prices from, deliberately, so a
figure produced here months after the fact and a figure produced at write time
cannot diverge in the last decimal places. Reimplementing either — even
faithfully — would make "why is this number this number" answerable two ways.

Since D-280 the writer resolves through ``pricing.load_price_book`` rather than
through ``resolve_price``, because one round trip per record was an N+1 on the
write path. **That does not weaken the sentence above**: the two resolvers are
held equal by ``test_the_batch_resolver_and_resolve_price_agree``, and
``compute_cost`` — which is where the last decimal places actually come from —
is still the one function both callers use. This pass keeps the per-candidate
resolver on purpose: it is operator-initiated and rare rather than on the write
path, and no performance requirement governs it. Batching it is available if
somebody measures it and finds it slow.

**Each candidate is resolved at its OWN ``created_at``**, exactly as the writer
does, and by the same half-open rule. A row added with an ``effective_from``
later than a call was made was not in force for that call, so that call stays
unpriced and stays on the worklist. Nothing here settles for the nearest row.

``call_record`` keeps its ``UPDATE`` grant for precisely this and for the A-099
caller-id upsert. It has no ``DELETE`` grant and nothing here wants one. No
trigger is involved: ADR-0025 rejects triggers as an enforcement device by name,
because a trigger is owned by the same role that owns the table.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.call_ledger.domain import CostStatus
from prope.call_ledger.pricing import compute_cost, resolve_price

#: The candidates. ``cost_status = 'unpriced'`` is served by
#: ``ix_call_record_unpriced_worklist``, the partial index over exactly this
#: status — so the scan is cheap over a state that is rare by design, and it
#: stays cheap as ``call_record`` becomes the largest table in the system.
#:
#: The two optional narrowing parameters let a caller reprice one newly-added
#: (provider config, model) pair rather than the whole workspace. Each appears
#: once, inside a ``COALESCE`` against its own column, so passing NULL means "do
#: not narrow" without needing a second statement or a type annotation on the
#: parameter. The tenant restriction comes from the session's policy, as
#: everywhere else in this module.
SELECT_CANDIDATES = text(
    """
    SELECT call_id, provider_config_id, upstream_model,
           input_tokens, output_tokens, created_at
    FROM   ledger.call_record
    WHERE  cost_status = 'unpriced'
      AND  provider_config_id IS NOT DISTINCT FROM
           COALESCE(:provider_config_id, provider_config_id)
      AND  upstream_model     IS NOT DISTINCT FROM
           COALESCE(:upstream_model, upstream_model)
    ORDER  BY created_at
    """
)

#: The status predicate appears here as well as in the selection, and not for
#: symmetry. Between the select and this update another writer may have priced
#: the same row; carrying the predicate into the update's own ``WHERE`` makes
#: that row simply not match, instead of being overwritten with a second
#: opinion. The ``rowcount`` this returns is therefore what actually changed,
#: which is what the caller is told.
UPDATE_TO_PRICED = text(
    """
    UPDATE ledger.call_record
    SET    cost         = :cost,
           currency     = :currency,
           price_row_id = :price_row_id,
           cost_status  = :priced
    WHERE  call_id      = :call_id
      AND  cost_status  = 'unpriced'
    """
)


@dataclass(frozen=True, slots=True)
class RepriceResult:
    """What the pass changed, and what it deliberately left alone.

    ``still_unpriced`` counts candidates that were examined and for which no
    price row was in force at their own timestamp. They remain on the unpriced
    worklist. It is reported rather than swallowed because "repriced 0" and
    "found nothing to look at" are different operational facts, and only one of
    them means somebody still owes a price row.
    """

    repriced: int = 0
    still_unpriced: int = 0

    @property
    def examined(self) -> int:
        return self.repriced + self.still_unpriced


async def reprice_unpriced(
    session: AsyncSession,
    *,
    workspace_id: str,
    provider_config_id: str | None = None,
    upstream_model: str | None = None,
) -> RepriceResult:
    """Give previously-unpriced calls the cost they were owed. Nothing else.

    ``session`` comes from ``workspace_transaction()``, so this pass covers
    exactly one workspace and the tenant policy applies underneath every
    statement. Like the writer, this function opens no transaction and does not
    commit — the caller's context manager owns the boundary, so a raise part-way
    through leaves the whole pass unapplied.

    Optionally narrowed to one ``(provider_config_id, upstream_model)`` pair,
    which is the shape of the operation someone actually performs: a price row
    for one model was missing, it has just been added, and only that model's
    backlog needs filling.

    Raises ``ValueError`` if a candidate prices to zero — the same refusal the
    writer makes, for the same reason. A ``priced`` row recording a cost of zero
    is refused by ``ck_call_record_cost_is_never_zero``, and neither storing it
    nor silently leaving the row unpriced would be true.
    """
    candidates = (
        (
            await session.execute(
                SELECT_CANDIDATES,
                {
                    "provider_config_id": provider_config_id,
                    "upstream_model": upstream_model,
                },
            )
        )
        .mappings()
        .all()
    )

    repriced = 0
    left_alone = 0

    for candidate in candidates:
        price = await resolve_price(
            session,
            workspace_id=workspace_id,
            provider_config_id=candidate["provider_config_id"],
            upstream_model=candidate["upstream_model"],
            at=candidate["created_at"],
        )
        if price is None:
            # Still no row in force at this call's own timestamp. It keeps its
            # tokens, keeps its status, and keeps its place on the worklist.
            left_alone += 1
            continue

        cost: Decimal = compute_cost(
            candidate["input_tokens"] or 0, candidate["output_tokens"] or 0, price
        )
        if cost <= 0:
            raise ValueError(
                f"{candidate['call_id']} reprices to {cost} against price row "
                f"{price.price_row_id}: {candidate['input_tokens']} input and "
                f"{candidate['output_tokens']} output tokens at "
                f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                "record cannot record a cost of zero, and leaving the row on the worklist "
                "would hide a price row that is itself the problem"
            )

        result = await session.execute(
            UPDATE_TO_PRICED,
            {
                "cost": cost,
                "currency": price.currency,
                "price_row_id": price.price_row_id,
                "priced": str(CostStatus.PRICED),
                "call_id": candidate["call_id"],
            },
        )
        # Counted from what the engine reports it changed, never from the branch
        # that intended to change it.
        repriced += result.rowcount

    return RepriceResult(repriced=repriced, still_unpriced=left_alone)
