# ADR 006: retain list order storage after the fixed-slot experiment

Status: decided; retain list storage. Final delivery identities belong to the
release acceptance/publication records. Date: 2026-10-17.

## Context and experiment

M4 asks whether replacing separately allocated order FIFO nodes with C fixed
slots offers a useful benefit at acceptable service and memory cost. The M3
baseline did not establish order allocation as a service bottleneck.

Control `97fdc6e` and candidate `4cf669f` share their tools, inputs and compiler
settings. Only the two OrderBook files differ. The candidate uses `size_t`
links and a free list, while retaining the price maps, OrderId hash reservation,
matching rules, pause/resume contract and one-frame network path.

## Decision

Retain the measured list control for production. The frozen rule requires
both mixed and cancel-heavy throughput to improve by a paired median of at
least 5%, with at least four improving pairs each. The verified five-pair
results are +5.241% (5/5) for mixed and +2.710% (4/5) for cancel-heavy.
The second mandatory threshold is not met. Service results cannot waive it.

The candidate and its source relation remain reproducible through the fixed
commits and M4 source archives. This is a completed negative decision
on the storage candidate; delivery has separate verification. The [report](../m4_report.md) and
[acceptance record](../m4_acceptance.md) track that work.

## Evidence and costs

The full [core comparison](../benchmarks/m4_core_pairs.md) keeps all 25 pairs.
Near-full reuse ranges from -23.848% to +24.712% per pair; median summaries
do not establish a stable advantage across that variation. Timed batches
are short, the VM shares its host, and the common 42 ns process p50 is near
the observed 41 ns clock step.

Separate Linux diagnostics confirm one fewer allocation per resting addition.
The actual 56-byte slots reserve 56,000 bytes at C=1,000 and increase empty
tracked requested heap bytes from 11,048 to 67,048. Instrumented constructor
medians rise from 83–84 ns to 916–958 ns; these are not production startup
measurements. Hash/price nodes still allocate, and RSS is a separate
whole-process observation. Allocation and layout changed together, so no
isolated cache or allocator explanation is claimed.

All 40 formal service measurements deliver and drain with Reference agreement.
Their four RTT p99 paired medians meet the +10% ceiling, but sweep's service
completion p99 increases by a paired median 26.438%, and mixed_4 has an
individual RTT p99 increase of 69.571%. These observations remain visible;
neither passing RTT medians nor reduced allocations negate the failed core rule.

## Reconsideration

A future milestone may revisit this tradeoff with a distinct workload need
or better-controlled measurement environment. M4 does not add candidates,
change its thresholds or extend repetitions to pursue a favorable outcome.
