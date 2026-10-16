# M2 service baseline

Status: implementation and verification in progress. See [progress](progress.md)
for observed results; this document describes the implemented interfaces, not a
release or performance claim.

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
