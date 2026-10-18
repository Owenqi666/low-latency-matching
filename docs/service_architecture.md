# Service architecture

This document describes the service's ownership, interfaces and resource model.
See the [project overview](../README.md) for capabilities and entry points, and
[progress](progress.md) for experiment and release records.

## Ownership and processing

The main/Gateway thread runs one Asio `io_context`. It owns connections, protocol
parsing, outgoing buffers and routing. One Matching worker owns the order book.
Boost.Lockfree SPSC queues carry commands to the worker and fixed-size Event/BBO
values back. A mutex and condition variable coordinate sleep and wake-up; the
service is not described as lock-free.

`MatchingEngine::begin()` fixes one command and its validation result without
changing the book. Each `next()` emits one business event into caller-reserved
storage. The synchronous M1 `process()` drains the same production state machine
and retains its `C+4` buffer and sequence checks. ReferenceEngine remains a
separate vector implementation with independent validation and matching.

Matching retains at most two pending service messages. A command's last mutation
is followed by an optional final BBO and its original Complete. These can be
published separately, including into a one-slot event queue. No later command
begins until the preceding Complete has entered the event queue. BBO does not
consume a business EventSeq; its watermark is the Complete sequence minus one.
Only changed best prices or best-level aggregate quantities produce an update.

When idle, the worker waits for commands or drain/abort. During a command it
waits for output space or abort. The Gateway continues reading events while
command admission is full. Its coalesced pump processes a bounded batch and
rechecks after clearing its scheduled flag, so publication during that transition
cannot leave work stranded. There is at most one queued pump notification.

## Connections and limits

The [protocol](protocol.md) uses explicit integer fields, an eight-byte header
and a 256-byte maximum frame. Default application limits are 64 live connections,
4 KiB received bytes and one decoded pending command per connection, 64 KiB
outgoing wire bytes per connection (including the in-flight write), and 1,024
effective slots in each queue. The order limit remains 1,000 by default.

Asio owns the progress of one read and one write per connection. A read buffer is
not rearranged while a read is outstanding. Outgoing values remain alive through
the write callback, including cancellation. Each connection's parsing budget and
the Gateway event budget are finite; pending connections rotate through service.
Budgets bound work per callback, not elapsed wall-clock latency.

### Capacity budget

Let `C` be the order limit, `Qc/Qe` the effective queue capacities, `N` the
connection limit, `S` the per-connection outgoing wire-byte limit and `R` the
experiment record limit. The following accounts for the actual containers in
[OrderBook](../include/llmatch/order_book.hpp),
[MatchingPipeline](../include/llmatch/pipeline.hpp) and
[Connection](../src/server.cpp); it is not an exact allocator or process-RSS bound.

| Storage | Capacity accounting |
|---|---|
| Resting orders | At most `C` list nodes containing `Order`, `C` hash-index nodes containing an ID and locator, and `C` price-level map nodes across both sides. The hash index reserves for `C` at load factor 0.75; bucket rounding, node links and allocator overhead are implementation-dependent. Total storage is `O(C)`, including the initially reserved buckets. |
| SPSC rings | `(Qc+1)*sizeof(AdmissionRecord) + (Qe+1)*sizeof(ServiceMessage)` bytes of element storage. Boost's runtime rings allocate one extra slot each. The worker additionally holds two pending messages and one current command/completion record. |
| Connection input | Each live connection has a 4,096-byte receive array and at most one `optional<Command>`, plus its socket and parsing state; default receive arrays alone total `64*4096 = 256 KiB`. |
| Connection output | The deque owns full `Frame` values plus a business flag; the active write remains in that deque. `S` limits encoded bytes, not allocated deque bytes. There is one 12-byte Welcome per connection; subsequent server frames are at least 58 bytes, so at most `1+floor(S/58)` frame values can be retained per connection, plus deque block/map and allocator overhead. |
| Experiment records | Two vectors reserve `R` admission and `R` completion records before the worker starts: nominal element storage `R*(sizeof(AdmissionRecord)+sizeof(CompletionRecord))`. `R=0` disables these records; exhausting a positive limit fails the experiment. |

A local arm64 macOS `sizeof` check gives `Order=40`, `Command=56`,
`optional<Command>=64`, `AdmissionRecord=72`, `CompletionRecord=56`,
`ServiceMessage=152` and `Frame=264` bytes. These are illustrative ABI sizes,
not measurements of Linux STL nodes. With those sizes, default rings use
229,600 bytes (224.2 KiB); `R=100501` records use about 12.27 MiB of elements.
An outgoing value with its flag and alignment occupies about 272 bytes, making
the default 64 KiB wire limit about 300 KiB of frame values per connection before
deque overhead. The 1,000 order values alone occupy 40,000 bytes; their list,
index and price-level nodes add to that figure.

The connection map, pump ID vector, Asio operation state, thread stacks, allocator
retention and OS socket buffers are additional costs. A closed connection retains
its in-flight buffer until its cancellation callback runs. No sum above is claimed
as a hard process-memory ceiling. Each run records `peak_rss_bytes` before
post-join snapshot/trace formatting; Linux `ru_maxrss` KiB is converted to bytes,
while macOS already reports bytes. For example, the separate verified
[profiling run](m2_profiling.md) recorded 37,855,232 bytes with four clients,
`C=1000`, `Qc=Qe=1024` and `R=100501`. RSS includes the server lifetime and setup,
and is reported alongside these logical capacity limits rather than inferred
from wire-byte high-water marks.

Welcome assigns a process-local, nonzero ClientId. RequestId correlates responses
without deduplication. ClientId, not a reusable socket descriptor or OrderId,
determines routing. Trade goes to maker and taker once each, or once total for a
self-trade. Other business events go to the requester. BBO broadcasts to current
connections; a new connection receives the Gateway's latest consumed snapshot.

A peer exceeding its outbound budget is explicitly disconnected. Admitted
commands and resting orders remain; results addressed to a disconnected identity
are consumed and counted as missing recipients. Reconnection gets a new identity
and cannot cancel the previous identity's orders. Restart creates an empty book;
there is no session, persistence or result replay mechanism.

On SIGINT/SIGTERM the server stops accepting commands, drains admitted commands
and output, then finishes pending writes within a finite deadline. Timeout or
worker failure exits nonzero. Socket write completion is not proof that a client
received a response. Counters distinguish publication, consumption, writes and
discarded/missing recipients.

## Evidence and build

An optional finite record limit preallocates admission and completion records.
Actual successful queue admission determines trace order. Matching timestamps
Complete publication and records event counts/digests. Formatting and file writes
occur after join; the core itself performs no I/O or clock reads. A full record
buffer ends the experiment explicitly, rather than truncating replay evidence.

`verify_service` replays the admitted trace through ReferenceEngine and checks
per-command event counts, wire-field digests, result status and the final snapshot.
Small tests additionally compare complete event values; digests do not constitute
a collision-free proof. A partially drained run is a failure artifact, not a
successful full-trace reference comparison.

Boost 1.89.0 is fetched from its [official archive](https://archives.boost.io/release/1.89.0/source/boost_1_89_0.tar.bz2)
with [published SHA-256](https://archives.boost.io/release/1.89.0/source/boost_1_89_0.tar.bz2.json)
`85a33fa22621b4f314f8e85e1a5e2a9363d22e4f4992925d4bb3bc631b5a0c7a`.
Asio and SPSC use headers; the offline verifier compiles Boost.JSON's provided
implementation in one translation unit to read evidence. Threads supplies the
platform threading link requirement.
ASan/UBSan and TSan use separate builds with instrumentation on production code.

Development Linux validation uses an Ubuntu 24.04 arm64 guest under QEMU/HVF on
macOS: four virtual CPUs, 4 GiB assigned RAM. This is a VM, not bare-metal Linux.
Environment probes detected a deliberate data race with Clang 18 TSan; actual
project test results are recorded separately. Software `perf` counters are
available with guest sudo, while hardware counters are unsupported in this VM.
