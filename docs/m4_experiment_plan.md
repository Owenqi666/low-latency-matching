# M4 order-storage experiment plan

Status: scope, workload design and adoption rules recorded before candidate
implementation or formal measurement. Short baseline allocation diagnosis and
common measurement-tool validation are in progress. Actual frozen A/B commits
will be recorded after those shared changes are complete.

## Baseline and question

The accepted baseline is `m3-experiments` at
`37220e16fe0f05110c5f4ea112e4057bc55be122`. Its exact-main
[push CI](https://github.com/Owenqi666/low-latency-matching/actions/runs/38992549856)
passed. The [M3 acceptance record](m3_acceptance.md) and release publication
receipt remain historical evidence, not validation of new M4 changes.

M3 rejected sixteen-frame writes because a one-client tail-latency regression
violated its frozen tradeoff rule. Production remains one-frame writes. M3's
optional storage experiment was not required or started; M4 selects a new,
bounded question rather than repairing incomplete M3 work.

Does replacing separately allocated FIFO order nodes with C preallocated slots
offer useful core throughput without unacceptable service or resource costs?
This is not a claim that order allocation is the service bottleneck. First
diagnose construction, setup and command allocation on short mixed,
cancel-heavy and near-full-reuse traces. Instrumented diagnostics are separate
from formal timing.

## One candidate

Preserve the bid/ask maps, OrderId unordered index and its reserve/load-factor
policy, matching interface, independent vector Reference, protocol, queues,
thread ownership, waiting and one-frame writes. Replace only FIFO node storage
and links with a fixed vector of C slots, head/tail indexes and a simple free
list. Slots never grow or become protocol identities. An inactive OrderId may
be reused; a slot's new occupant has the new order's identity and arrival order.

Matching continues to query each maker anew and copy it before fill may erase
the node. Full-capacity limit admission still rejects before matching; market
IOC needs no resting taker slot. No generation handles, allocator framework,
runtime storage modes or second optimization are introduced.

Common tools and behavior tests land before freezing the list control A.
The slot candidate B then changes only the storage implementation and any
strictly necessary storage-specific validation. Separate commits/builds
preserve both. Production ultimately retains one selected path; rejected source
remains rebuildable in the release archive.

## Frozen inputs and execution

All formal runs use Linux unsanitized Release and the same compiler, flags,
input bytes, C=1,000 and common measurement tools. Record clean source identity,
actual binary hashes, environment, host/guest resources and uncontrolled
affinity/frequency/background load. No concurrent build, test, compression or
profiler runs during formal measurement. Existing pinned dependencies and the
project's Linux VM may be reused; fresh-install reproduction is a separate gate.

Core: the existing mixed, cancel_heavy, sweep and clustered generators/seeds,
each with 100,000 commands, plus near_full_reuse with seed 20261020. The latter
starts with C bids, IDs 1..C, quantity 10, owner 1 and sixteen sparse prices
`8000 + ((OrderId - 1) % 16) * 64`. Every 35-command cycle contains one valid
new limit rejected at capacity, sixteen cancel/reinsert pairs and one market
sell/reinsert pair. Reinsertion reuses the removed ID and price with alternating
owner 1/2. The market consumes the best-price FIFO head completely. Market and
rejected-limit IDs increase above C. Truncate exactly at command 100,000;
expected outcomes are 2,858 CapacityExceeded rejections and 97,142 accepted
commands, with live depth 999..1000. A separate ledger and Reference verify
these properties rather than trusting the generator's description.

Each of the five scenes has five pairs, ordered AB/BA/AB/BA/AB. Each invocation
starts fresh engines and includes independent warmup and validation, then one
latency and one throughput interval. Total: 25 pairs, 100 timed intervals.
The M4 pair summary verifies all five pairs; a single repeats=1 report is not
itself a five-round formal result. Existing timing boundaries, full-event
Reference comparisons, counters, checksum, snapshot checks and clock probe
remain intact. Report every round's absolute values, paired change and range;
short batch duration and clock quantization remain explicit limitations.

Service: mixed_1, mixed_4 and sweep_4 at 10,000 requests/s, plus burst_4 at
2,000/s average with a 100 ms period and 10 ms window. Five pairs per scene,
AB/BA alternating, a new server each attempt and one separate warmup per
variant/scene: 40 measurements plus eight warmups. Use at least 100,000 completed
samples and a plan window of at least ten seconds; burst takes about 50 seconds.
Use the M3 background depth 500, working depth 64, command/event capacities
1024, send limits 65536, inflight 16384 and five-second drain/shutdown limits.
The explicit `m4-formal` subset must not weaken the old seven-scene `formal`
contract. Failed attempts remain recorded; no reduced rate or larger buffers.

Every drained service trace is independently checked against actual admission
order. Evidence validity, sample sufficiency, internal drain and full client
delivery remain separate outcomes. Report core timing, service completion and
RTT separately, with send lag, queue observations and lifetime CPU/RSS scope.
No new high-load/overload capacity claim or 45k/80k extension is planned.

## Allocation, initialization and memory

A separate diagnostic executable counts allocation/free requests and requested
bytes around construction, setup and measured limit/market/cancel calls.
Parsing, Reference, snapshots and formatting stay outside counted phases.
Any allocation-wrapper or instrumentation overhead is disclosed; diagnostic
timings do not replace uninstrumented core results. Record empty/near-full
requested live bytes, constructor observations and slot size times C. Process
RSS includes other allocations and allocator behavior, so it is not slot-only
memory. Map/hash nodes and the rest of the service still allocate.

## Frozen adoption rule

1. Correctness, fair input/capacity, complete evidence and all forty formal
   service deliveries/drains pass.
2. For both mixed and cancel_heavy, median paired completed commands/s change
   `100 * (B / A - 1)` is at least +5%, with at least four of five pairs improving.
3. Each other core scene's paired throughput median regresses no more than 5%.
   Every service scene's paired RTT p99 median regresses no more than 10%.
4. Report initialization, memory, other latency/resource results and complexity
   costs. A numerical pass permits, but does not compel, adoption. Evidence
   indistinguishable from noise supports retaining the list implementation.

These thresholds select the production implementation, not whether M4 can
finish. Do not tune them after results, discard slower rounds, add another
optimization or repeat indefinitely to obtain a favorable conclusion. A rejected
candidate still proceeds through report, clean reproduction, exact-source CI and
verified release. Allocation and locality change together, so their individual
causal contributions are not isolated by this experiment.

## Validation and delivery

Keep the existing tests and add only behavior/invariant coverage for capacity,
FIFO removal, slot/OrderId reuse and pausing across reclamation. Adjust the old
OrderBook(1)-with-256-orders white-box test to sufficient storage capacity;
do not silently expand the candidate. A/B and the final path each have a
100,000-command Reference validation, reusing formal traces where applicable.

The candidate needs actual Debug/Release/ASan-UBSan/independent TSan CI evidence
even when rejected. Discovery/JUnit and required groups must agree without
skips. Preserve core and seven-scene service CI smoke, independently validate
downloaded artifacts and add focused corrupt-evidence tests for new contracts.
No shared-runner absolute performance gate is added.

After selecting production, reproduce from a fresh public Linux checkout with
fresh dependency/build directories: full Release tests, two CLI clients, core
and service smoke, and a labeled short representative A/B check. Inspect latest
PR head/base/checkout and artifacts, merge normally, then inspect the new exact
main push CI and downloaded artifacts. Archive all source relationships, raw
attempts, checksums and acceptance evidence, publish `m4-order-storage` at that
main, and verify the uploaded assets and publication receipt. Original planning
documents and VM/SSH material remain local. See [M4 acceptance](m4_acceptance.md).
