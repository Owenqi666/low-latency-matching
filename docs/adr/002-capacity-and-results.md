# ADR 002: conservative admission and bounded synchronous results

Status: implemented in the M1 baseline.

## Context

A limit can trade and then need space for a remainder. Rejecting only after the
trades would require rollback or a different business contract. A command can
also consume many resting makers, so its number of events is not constant.

## Decision

If the initial live count is C, reject every new limit before any matching.
Markets and cancellations remain available. Active duplicate IDs and ownership
errors are likewise resolved before mutations. This is deliberately conservative:
a crossing limit that would free space is still rejected on a full book.

The caller supplies a reusable span of at least C+4 fixed-size Event values.
At most C makers yield C trades, plus Accepted, at most one remainder event,
and Complete: C+3 events. The extra slot is conservative slack. Configuration
checks ensure both the count and allocation byte count are representable.
No result vector grows inside process().

Call-level capacity and sequence checks run before any write or mutation. A call
error leaves the book, both counters and all output bytes unchanged. Business
rejections consume sequence numbers and produce Rejected followed by Complete.
Every event is initialized as a value so a reused slot cannot retain Trade data
when it later contains a rejection or cancellation.

## Consequences and alternatives

Pre-scanning a full book could admit more crossing limits but adds a second
matching pass. Reserving/restoring state could change semantics and complexity.
Neither is needed for this baseline. Unrecoverable allocation failure terminates
the run; no exception-catching layer attempts to continue a partially changed
engine or call that failure a business rejection.

This result bound depends on a finite active-order capacity. It costs C+4 Event
slots per caller and is measured/reported with the benchmark. The array is not a
network backpressure mechanism: M2 must pause command execution when a bounded
event channel cannot accept more output, without letting later commands overtake
the paused command. That change has its own concurrency and shutdown acceptance.

Exact full-book fixtures, maximal maker sweeps, byte sentinels, reused buffers
and near-maximum sequence tests verify the chosen contract.
