# Scheduler protocol migration v2

## Status

F6A ratifies the pure scheduler v2 ordering but does not switch live Kernel or
replay semantics.

## Problem in v1

Historical scheduler v1 orders ready mailbox work by receiver `entity_id`.
Because an entity ID includes a caller-chosen label, a caller can grind labels
offline and obtain permanent lexicographic priority. A continuously refilled
low-ID mailbox can starve an older message in another mailbox.

## Ratified v2 ordering

For `PROCESS_MESSAGE`:

`(rank, enqueue_logical_clock, entity_id, mailbox_index, message_id)`

The enqueue logical clock is assigned by committed history, globally monotonic,
and replayable. A later refill cannot overtake an older queued message merely by
grinding an entity ID.

For lifecycle activation:

`(rank, founding_index, entity_id, mailbox_index, message_id)`

The founding index is kernel-assigned and monotonic.

No persistent scheduler cursor is introduced.

## Compatibility boundary

v1 remains a named historical protocol. Existing committed histories must never
be replayed under v2.

F6B must make scheduler protocol an explicit genesis input instead of mutating
the historical v1 constant in place.

Required F6B behavior:

1. `genesis_descriptor_digest` accepts an explicit scheduler protocol.
2. A non-empty pre-v2 history without new protocol metadata is treated as v1
   and must replay exactly.
3. A newly created empty history selects v2 before its first committed event.
4. Once a history has committed its first event, its scheduler protocol is
   immutable for that history.
5. Replay applies the scheduler profile bound by that history's genesis.
6. No in-place v1-to-v2 event-chain rewrite is permitted.
7. Any future state-transfer migration creates a new history/new genesis rather
   than altering the old chain.
8. Protocol-selection metadata, if stored for discoverability, is not alternate
   authority and must reconcile to genesis/state-root evidence.

This preserves old-history compatibility while stopping creation of new
grindable histories after F6B lands.

## F6B integration disposition

F6B implements the migration boundary without mutable sidecar authority.

- empty fresh histories select v2 at `Kernel.open()`;
- nonempty histories are classified by matching the first committed
  `before_state_root` against v1 and v2 genesis candidates;
- exactly one candidate must match;
- explicit caller selection must reconcile to the committed profile;
- standalone replay/project/analyze APIs remain v1 by default unless an
  explicit scheduler profile is supplied;
- no existing event chain is rewritten.
