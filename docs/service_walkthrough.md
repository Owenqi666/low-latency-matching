# Following one request through the M2 service

This guide follows the implemented service and its test entry points. It is a
reproduction and explanation aid; it does not record personal learning outcomes
or replace the [M2 acceptance record](m2_acceptance.md). The
[protocol](protocol.md), [architecture](service_architecture.md), and
[measurement method](service_benchmark_method.md) specify the wider contracts.

## From fragmented bytes to an admitted command

Start in [Connection::read/process_input](../src/server.cpp). The Gateway's only
`io_context.run()` thread owns each socket, its 4 KiB receive array, and at most
one decoded pending command. `protocol::inspect()` checks the first frame without
assuming a TCP read equals a message: fewer than eight header bytes means wait
for eight; a complete valid header gives the exact required frame length. The
codec rejects bad version/type/length before waiting for an untrusted payload.

Once that frame is complete, `decode_request()` binds it to the connection's
server-assigned ClientId. The consumed prefix is removed, and any following
frames remain within the same bounded buffer. Zero quantity, invalid side and
other representable business errors still reach Matching. They are rejected in
the existing M1 order; they are not protocol failures.

`MatchingPipeline::try_submit()` in [pipeline.cpp](../src/pipeline.cpp) timestamps
and attempts the command-queue push. Only a successful push increments admitted
work and appends the experiment admission record. A full queue leaves that one
command pending in the connection. No further read or parse is started there
until admission can progress. Reading bytes and decoding a frame therefore do
not imply business Accepted, or even service admission.

The Gateway continues consuming output and servicing other sockets while input
is full. Its pump handles at most 128 output messages per callback; each
connection's input processing has a 16-iteration budget, and the starting
connection rotates. `schedule_pump()` coalesces notifications with an atomic
flag. `rearm_pump()` clears it and checks output, runnable input and worker
termination again, covering work arriving while a notification was already set.
These are work budgets, not a wall-clock latency guarantee.

The codec tests enumerate incomplete prefixes and chunk sizes. The real TCP
`ServiceTest.test_fragmented_and_coalesced_requests` also sends byte-sized
requests, concatenated frames, and a burst crossing both the input budget and
4 KiB receive buffer.

## Pausing a sweep without a whole-command result array

The worker in [MatchingPipeline::run](../src/pipeline.cpp) alone owns
[MatchingEngine](../src/matching_engine.cpp). `begin()` fixes a command and its
validation result; `next()` advances only enough to produce one business event.
The synchronous M1 `process()` drives these same transitions into its `C+4`
output span. [ReferenceEngine](../reference/reference_engine.cpp) remains an
independent vector model.

The worker checks for output space before advancing. It retains at most two
fixed `ServiceMessage` slots. A full event queue stops further matching and
prevents the next command from starting. A sweep across 64 makers can therefore
run through an event queue of capacity one without allocating a 64-event staging
array. Once the Gateway pops output, its notification lets the worker continue.

Waiting uses one mutex/condition-variable protocol. An idle worker waits for a
command or drain/abort; an active worker waits for output space or abort. A drain
request does not bypass output backpressure. Push/pop and stop requests notify
under the same mutex used to check the wait predicate. Tests use a controlled
notification barrier to place a space-release or stop notification before the
worker's next wait; they do not depend on a long sleep finding that interleaving.

The entry points are `PausableEngineTest.*` and `PipelineTest.*`, particularly
`TinyEventQueuesSweep64MakersWithOrderedBboAndComplete` and
`FullInputAndOutputDrainAfterNotificationBeforeWait`. They compare complete
events, sequence numbers and final snapshots against ReferenceEngine.

`AbortAfterFirstTradePreservesCompletedPrefixAndPartialBook` holds a notification
barrier immediately after the sweep's first published Trade, queues a later
cancel and requests abort. It checks the two completed setup commands, the
unfinished sweep's admission/phase, the still-full output slot and the partial
book. It deliberately distinguishes that partial state from replaying the whole
admitted trace to completion.

## Maker delivery, final BBO and Complete

`MatchingServer::route()` uses the identities carried by each event. Accepted,
Rejected, Rested, Cancelled and Complete go to the requester. Trade goes to maker
and taker, with one copy total if both belong to the same client. It does not
look up the current owner of a reusable OrderId or route by a socket descriptor.
The Trade's request fields still identify the active/taker command.

This is why the CLI keeps its network read active even when stdin is idle. In
[client_main.cpp](../apps/client_main.cpp), an unsolicited maker Trade is printed
without completing a pending local request. For local requests, the first
Accepted/Rejected is associated in FIFO order and establishes CommandSeq;
Complete ends that command. Repeated RequestIds do not overwrite a map entry.

When `next()` yields Complete, the worker reads the final top of book. If best
price or aggregate best-level quantity changed, it holds BBO then Complete in
its two slots. They can enter a one-slot queue on different iterations. Only
after Complete is published may another command begin. BBO has the same
CommandSeq, a watermark of `Complete.event_seq - 1`, and no new business EventSeq.
Deep-level changes and rejections that leave the quote unchanged emit no BBO.

The Gateway caches the last BBO it consumed. A new connection receives Welcome
and that snapshot in order, followed by later updates. This is a Gateway-consumed
watermark; it is not an unsynchronized read of the worker's current book.
`ServiceEvidenceTest.test_full_network_events_routing_and_bbo_match_independent_reference`
derives expected BBO from reference prefix snapshots and compares complete
per-client streams, including a connection joining after existing orders.

## A two-client demonstration

Run the following from the repository root after the [README](../README.md)
build steps. Use a new evidence directory for each attempt. Terminal A starts
the server; wait for its `READY 19999` line before connecting:

```sh
./build/debug/matching_server --port 19999 --record-limit 100 \
  --output-dir build/demo-service-1
```

In terminals B and C, each run:

```sh
./build/debug/matching_client --host 127.0.0.1 --port 19999
```

Enter these lines in order, waiting for the corresponding CommandComplete
before the next numbered step. Keep both clients connected until step 5.

| Step | Terminal | Input | Observable result |
|---:|---|---|---|
| 1 | B | `limit 1 101 sell 100 5` | Rested quantity 5; ask BBO at 100/5 before Complete |
| 2 | C | `market 1 201 buy 2` | Both clients receive the same Trade; idle B receives its maker notification; ask quantity becomes 3 |
| 3 | C | `cancel 2 101` | Rejected with NotOwner, then rejected Complete |
| 4 | C | `limit 3 202 buy 90 0` | Rejected with InvalidQuantity, then rejected Complete |
| 5 | B | `cancel 2 101` | Cancelled remainder 3; ask becomes absent, then Complete |

The CLI prints JSON lines containing all event identities, quantities, completion
status and BBO fields. ClientIds are assigned by the server; do not assume they
are fixed across experiments. Enter `quit` in B and C after the results arrive,
then press Ctrl-C in A. The CLI drains its outstanding requests with a five-second
deadline. The server's final counters should show five admitted and five
completed commands. Validate the saved business results after it exits:

```sh
./build/debug/verify_service --directory build/demo-service-1
```

This last check replays actual admission order, command digests and the final
book. The separate full-event test above provides stronger small-case routing
and BBO comparison; a digest alone is not collision-free proof.

## Slow peers and shutdown

`Connection::enqueue()` counts outgoing wire bytes including the in-flight
`async_write`. Each connection has only one such write at a time, and the frame
storage survives cancellation until its callback. A frame that would exceed the
limit causes `slow_client` closure. Already admitted commands still execute and
resting orders remain. Results for the disconnected identity are consumed and
counted as missing/discarded delivery. A reconnect gets a new identity and cannot
cancel those retained orders.

The reconnect test observes the old socket's EOF before connecting again. On
Linux it reads `/proc/<pid>/net/tcp` and `/proc/<pid>/fd` to prove the server
reused the descriptor while assigning a different ClientId; macOS runs the same
ownership/Trade checks without claiming to have observed descriptor reuse. The
restart test launches a separate process and checks its zero-watermark empty
BBO and UnknownOrder rejection for an order retained by the previous process.

Use the existing bounded real-socket examples; they retain commands, client
streams, server counters and stderr under the selected artifact directory:

```sh
LLMATCH_SERVICE_ARTIFACTS=build/demo-slow-peer \
  python3 tests/service_test.py build/debug/matching_server \
  ServiceTest.test_slow_client_is_closed_while_healthy_client_keeps_completing -v
LLMATCH_SERVICE_ARTIFACTS=build/demo-shutdown \
  python3 tests/service_test.py build/debug/matching_server \
  ServiceTest.test_blocked_socket_shutdown_deadline_is_failure_with_delivery_evidence -v
```

The first test leaves one maker unread, constrains its socket/send buffers, and
checks that a healthy taker completes 1,000 requests while the slow client is
closed. The second allows a larger backlog and uses a 100 ms shutdown deadline;
the test passes only when that server attempt exits nonzero with discarded
delivery evidence. A passing failure-path test is not a successful service run.

On SIGINT/SIGTERM, `begin_shutdown()` stops accepting/admitting, requests worker
drain and keeps the event pump alive. `maybe_finish()` waits for worker completion,
an empty event queue and empty live-connection send queues. Deadline exhaustion
requests abort and records failure. `run()` joins the worker before the main
program formats evidence. Socket write completion is still only local delivery
progress; it does not prove the peer consumed Complete. The report separates
admitted/completed, published/consumed and written/missing/discarded counters.

`ServerLifecycle.GatewayCallbackExceptionAbortsAndJoinsWorker` posts a controlled
exception into the actual Gateway event loop through the existing test friend.
It checks nonzero `run()`, failure text and a joined/aborted worker. It adds no
production fault-injection option.

## Reading open-loop evidence

In [loadgen_main.cpp](../apps/loadgen_main.cpp), requests, frames, offsets and
sample storage are prepared before measurement. All connections first receive
Welcome; setup completes sequentially outside the measured phase. `schedule()`
then selects commands by absolute planned times, independently of responses.
It never shifts the schedule to wait for a preceding Complete.

At a due time, a full global in-flight budget or per-connection send budget marks
that planned request `not_started` with a reason. Enqueued requests may still wait
behind the connection's current write. `first_attempt_ns` is recorded immediately
before that request's first `async_write`; send lag includes this wait and any
late scheduler dispatch. RTT runs from first attempt to receipt of the full
Complete frame. Write-completion and receive callbacks can be observed in either
order, so socket write completion is not the RTT endpoint.

The deadline is measurement start + final planned offset + drain allowance.
Every planned sample remains in CSV, including not-started, failed and unfinished
requests. The JSON counters enforce `planned = not_started + started` and
`started = completed + failed + unfinished`; only completed requests have RTT
percentiles, and business rejection is a completed outcome. Setup has its own
samples/counts. Run the README's network smoke, then independently rerun
`scripts/summarize_service_bench.py` on its output. Inspect send lag and loss counts
alongside RTT rather than treating a short completed subset as the whole load.
