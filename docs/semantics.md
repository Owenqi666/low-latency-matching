# M1 semantics (contract v1)

Single instrument, continuous matching, integer ticks and quantities, one thread,
in-memory state. Buy takes the lowest ask; sell takes the highest bid. Equal
prices use ascending arrival sequence, unchanged by partial fills. Each trade
uses the resting maker price. Self-trading is allowed.

## Identity and validation

ClientId is uint32; RequestId, OrderId, Quantity and sequences are uint64;
Price is int64. All IDs must be nonzero. RequestId correlates results and is not
deduplicated. OrderId is globally unique among active orders; completed or
cancelled IDs can be reused. A later cancel targets the current generation of
that ID: M1 does not detect stale requests, authenticate clients or recover sessions.

The exact rejection precedence is:

1. InvalidClientId, InvalidRequestId, InvalidOrderId, InvalidSide (in that order).
2. InvalidQuantity, then InvalidPrice (price applies only to limits).
3. DuplicateOrder for a new order; UnknownOrder then NotOwner for a cancel.
4. CapacityExceeded for a limit when the initial live count equals capacity C.

Limits require 1 <= price <= max_price and all new orders require
1 <= qty <= max_order_qty. A full book rejects every new limit before matching,
including a limit that could immediately fill. Market and cancel still run.
Market orders use IOC: their unfilled quantity is cancelled, never rested.
Cancel removes all remaining quantity of a live order, after checking ownership.

Configuration requires C > 0, max_price > 0, max_order_qty > 0,
C <= UINT64_MAX / max_order_qty, and representable C+4 and (C+4)*sizeof(Event).
Invalid configuration throws std::invalid_argument before processing any command.
No price*quantity settlement arithmetic exists in M1.

## Calls, sequences and events

Both counters start at zero; the first processed command and event are 1.
`process(command, span)` first requires at least C+4 Event slots, then requires
one remaining command sequence and at least C+4 remaining event sequences.
The precedence of call errors is OutputBufferTooSmall, then SequenceExhausted.
Either returns event_count=0 with book, counters and ALL output bytes unchanged.
Checking conservative sequence space can reject a call that would emit fewer
events. Counters never wrap. Business rejection consumes command/event sequences.

Success emits Accepted, then Trade events in matching order, then at most one
Rested or Cancelled(IocRemainder), then CommandComplete(Accepted).
Successful cancel emits Accepted, Cancelled(UserCancel), CommandComplete(Accepted).
Rejection emits Rejected(reason), CommandComplete(Rejected), with zero result quantities.
Fully filled orders produce no zero-quantity Rested or Cancelled event.

Every event carries command kind, command/event sequence, requesting client,
RequestId and target OrderId. Trade additionally names maker and taker identities,
their arrival sequences, price and quantity. Rested records side, price, remaining
quantity and arrival sequence. Cancelled records quantity and reason. Complete
records filled, resting and cancelled quantities. Unused fields are zero/default;
`Side::Buy` and `CommandKind::Limit` have underlying value zero.

For new orders: submitted = filled + resting + cancelled. A cancel completion
reports only the quantity removed. Complete means immediate command processing,
not the eventual lifetime completion of a resting order. At most C+3 events are
possible; C+4 is the fixed conservative output contract. Only the returned prefix
is valid; caller consumes it before reusing the buffer.

Allocation failure is fatal to the run: exceptions propagate to the CLI boundary,
which reports failure and exits. There is no transactional rollback or attempt
to keep using an engine after an unrecoverable exception.

## State and implementation boundaries

Canonical snapshots list bids descending, asks ascending and orders FIFO within
each level; they include every Order field and level totals. No empty levels,
zero remaining orders or duplicate live IDs are allowed. After every command,
if both sides exist, best_bid < best_ask.

Book/engine instances holding iterators cannot be copied or moved. Core has no
file I/O, logging, clock reads, networking or test dependency. Full invariants and
snapshots are validation operations outside benchmark timing. ReferenceEngine
shares value contracts but implements matching and validation independently.

The service adds a [pausable execution and backpressure design](service_architecture.md)
around these matching semantics. This document's synchronous full-result-array
contract describes the core entry point; the service emits results incrementally.
