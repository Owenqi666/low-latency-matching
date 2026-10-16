# M1 walkthrough

This guide supplies reproducible exercises. It does not claim the reader has
already demonstrated mastery of them.

## Follow a partial fill

Run `replay --engine compare` on `data/fixtures/basic.trace` using the README
command. The third command buys 8 with limit 101. Maker 101 rests first at 100
with quantity 5; maker 102 follows at the same price with quantity 7. The events
are Accepted, Trade(101,5@100), Trade(102,3@100), Complete(filled=8). Maker 102
keeps its original arrival sequence and its remaining quantity is 4.

Explain why the taker's price 101 is a crossing condition but not the execution
price, and why a partially filled maker does not move behind later orders.
Compare the events to `tests/fixtures.hpp`, not merely to the final total.

## Follow a removal

In `OrderBook::apply_fill`, find the ID, subtract from both remaining and the
level total, then remove a zero-quantity node through `erase_node`. That helper
copies its locator, erases the hash entry, erases the list node, and finally
erases the empty level. Explain which references are invalid after each step.
The matching loop copies the maker's business fields before this operation so
its Trade construction never reads a destroyed list node.

## Reproduce a differential failure

`docs/t06_evidence.md` describes a temporary copy of the production source with
maker price incremented by one. The first mismatch in its generated trace was
an event value even though the final book could still be correct. Chunk deletion
reduced 2,000 commands to the two-command `data/regressions/maker-price.trace`.
Each candidate replays from empty engines; unknown cancellations created by
deletion remain part of the input. The reduced case remains in normal CTest.

Explain why selecting only candidates that retain the failure class matters,
and why the fixed implementation correctly refuses to shrink that now-passing
case. The mutation was a test probe, not a defect claimed to have occurred in
the original engine.

## Read a core benchmark

Use `docs/benchmark_method.md` with `docs/m1_report.md`. Identify input/config
hashes, setup state, code version, compiler settings, result-buffer size and the
individual rounds. Explain which work lies inside each timing interval and why
latency-mode sample averages are not the independently timed throughput result.
Follow one accepted command and one rejection through the grouped distributions.

M1 has no network queue or client RTT. Its complete event marks the immediate
command result, not the end of a resting order's future lifetime. M2 must add
pausable output and backpressure before claims about a concurrent service apply.
