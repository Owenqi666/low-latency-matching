# Gateway diagnostics: hypotheses and observation contract

Status: G03 implemented and under cross-platform integration verification, before
G04 measurements. No new bottleneck or performance result is established here.

## Questions to resolve

| Hypothesis | Required observation | What that observation cannot establish alone |
|---|---|---|
| Existing queued-frame batching reduces application write overhead | write operations/admitted, submitted frames/operation, batch distribution, whole-callback duration; separate syscall profile | One async_write is a composed operation, not one syscall |
| Single-client tail regression involves output completion or Gateway scheduling | Same-process window samples, output/in-flight state, callback intervals and loop timer lateness, alongside service and client samples | Lifetime high-water/histograms alone do not establish ordering or causality |
| SlowClient reflects Gateway or peer/output congestion | Connection close snapshot, outstanding frames/bytes, last callback, queue states and delivered/missing recipients | The close reason does not prove the peer stopped reading |
| Load generation constrains delivered offered load | Scheduled-to-start lag over planned-time windows, actual sending interval and pending sends | Eventual completion does not prove stability at the advertised offered rate |

## Thread and lifetime boundaries

Connection, SendQueue and Gateway diagnostic state are owned by the Gateway
thread. The worker's non-atomic PipelineStats and completion vectors are read
only after join. Live queue depth must use the producer-side command queue and
consumer-side event queue availability APIs, not the worker's mutable counters.
schedule_pump can run on both threads and must not write an unsynchronized timing
field. A Gateway timer measures its own scheduled-versus-actual callback time.

Closing snapshots are taken before SendQueue discards queued/in-flight frames.
Late callbacks must still count as unconfirmed under the existing semantics and
must not produce duplicate close records. Successful socket writes do not imply
application-level peer receipt. Existing basic server.json field meanings remain
unchanged; detailed records are an optional, separately versioned artifact.

## Implemented observation bounds

Enable detailed collection with `--gateway-diagnostics 1` and use `--output-dir`
to retain its artifacts after shutdown. The default is off: no detailed collector,
timer or detailed clock collection is created on that path. Optional collection
uses 128 close records, 4,096 global windows, 16,384 connection windows and three
64-bucket histograms. The collector occupies 2,442,960 bytes on the current arm64
build; per-connection SendQueue observation fields are additionally bounded by
the existing maximum connection count. No background thread or hot-path file
writes are introduced.

The nominal sample period is 10ms, scheduled after each actual callback, without
catch-up bursts. At 64 persistent connections, connection records may cover only
about 2.56 seconds even while global windows cover about 40.96 seconds; callbacks
delayed by load stretch those times. These are capacity examples, not measured
coverage guarantees. JSON and CSV files report actual timestamps, retained first
and last times, and separate overflow counts. Only observed windows support claims.

`gateway_diagnostics.json` describes schema, clock, bounds, coverage and duration
histograms. `gateway_windows.csv` holds global counters/deltas and safe queue
occupancy snapshots. `gateway_connections.csv` holds per-connection outbound
state at those times. `gateway_closes.csv` records each retained pre-discard close
state and reason. Total bytes/frames already include in-flight storage; queued-only
state is their difference. An in-flight operation retains its entire batch until
the composed callback, even after an underlying partial socket write.

The optional checker in `summarize_service_bench.py` validates headers, record
bounds, overflow accounting, histogram extrema, callback/close totals, ClientId
ranges, batch/allowance high-water bounds, window deltas and time association.
Legacy reports without the new switch remain readable. Disabled runs reject
stale detailed artifacts. Tests mutate real artifacts to check rejection rather
than merely checking that serialization reproduces its own values.

Local checks include actual Asio timer delivery and cancellation at shutdown,
real TCP traffic with ten live windows in the observed test, controlled storage
overflow, and existing short-write/cancel/late-callback/duplicate-close cases.
The selected 17-test Gateway/network group passed; final Linux/sanitizer checks
and experiment-source identities remain part of the delivery gate.

Profile only representative mixed_1/mixed_4 runs outside performance timing.
Record per-thread CPU, scheduling/context switches and available syscall/call-stack
data. Tool/permission limitations remain explicit. Cross-process association must
state host clock/alignment; clocks from different machines are not subtracted.

## Result ledger

Pending G04. Each eventual finding will list its source identity and raw evidence,
the direct observation, supported explanations, remaining alternatives and scope.
External 10k/s reports remain reproduction leads until this environment supplies
its own result.
