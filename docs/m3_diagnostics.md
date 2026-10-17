# M3 baseline diagnostics and experiment selection

Four separately instrumented baseline runs support testing bounded multi-frame
socket writes. The two repeated mixed workloads each made about 702,000 Gateway
`sendto` calls for 100,001 measured requests plus setup. The 45,000/s workload
made 3,151,699 calls. These three counts equal their respective complete-frame
write counters; the unchanged implementation initiates one Asio write per frame.
This is evidence for a specific experiment, not proof that sending is the sole
bottleneck or a prediction of speedup.

All four diagnostic workloads and their four independent warmups completed their
plans, drained and passed full Reference replay. The existing independent
summarizer passed in the guest and again on the host, with identical reports.
These instrumented latency and resource observations are excluded from formal
M3 A/B timing and do not replace it.

## Source, execution and environment

- Source: clean detached `db9b74f4181a2dc4a50966c20080949c839bf73f`, matching
  the fetched `m2-service` tag and `origin/main` when the diagnostics started.
  The existing guest checkout was advanced from `eb0a109`; configure succeeded
  and Ninja reported no work. No production source was changed.
- The server, corrected loadgen and verifier SHA-256 values remain those in the
  [M2 report](m2_report.md#source-and-environment). Exact hashes, compile commands
  and source cleanliness are saved in every manifest and post-run profile.
- Linux Ubuntu 24.04 arm64 in the retained QEMU/HVF VM, four vCPUs and 4 GiB RAM;
  GCC 13.3, unsanitized Release. The existing disk booted kernel
  **6.8.0-147-generic**, whereas M2 measurements used `6.8.0-142-generic`.
  No kernel change was made by this diagnostic task. Historical M2 results are
  consequently not substituted for a fresh formal control group.
- Physical host: Apple M5 Pro, 18 cores, 48 GiB RAM, macOS 26.6.2; no exclusive
  physical core, affinity or frequency control. Server and loadgen share guest
  TCP loopback. No guest builds or competing benchmark runs occurred during
  these measurements. Brief evidence reads and monitoring add overhead.
- Executor: Codex subagent `m3_scope_review`. Raw profile attachment windows are
  recorded individually, from 2026-10-17 00:39:00 through 00:39:56 UTC. This is
  neither a human performance assessment nor a bare-metal/cross-machine result.

The helper imports the existing workload generator, `run_service_bench.run_one`
and summarizer. It runs in calibration mode: 10,000/s mixed twice, 45,000/s mixed
once, and the existing 2,000/s-average temporal burst once. Each has a separate
1,000-command warmup and 500 setup orders. Mixed plans run for ten seconds;
the shorter burst has 20,001 requests across approximately ten seconds rather
than M2's 100,000-request, approximately fifty-second formal burst. Original
scenario seeds, generator, 1,000-order capacity, 1,024-slot queues, 65,536-byte
send limits and five-second drain/shutdown limits are preserved.

## What the instruments observe

After server READY, `perf stat --per-thread` attaches to the existing Gateway
and Matching TIDs. It counts task-clock, context switches, migrations, page
faults, and syscall-entry tracepoints for sendto/sendmsg/write/writev,
recvfrom/recvmsg and futex. Each command has a thirty-second hard bound.

After the loadgen starts, a separate `perf record -e cpu-clock -F 499
--call-graph dwarf,8192` attaches to both processes. Unlike M2's user-only
sampling, this captures available user and kernel paths. The helper also saves
50 ms `/proc/<pid>/task/<tid>/stat` observations and the loadgen child's resource
usage. Gateway is the server's initial/main TID; Matching is its existing worker.
Loadgen's small auxiliary signal thread is retained in the raw observations.

Attachment is asynchronous and includes setup. Stat, sampling, `/proc` and
process-lifetime windows are not identical or synchronized to the first measured
request. Task-clock is CPU time within the attachment, not wall-clock latency;
the `/proc` observations are quantized and end at the last successful sample.
Loadgen child resources include parsing, setup, measurements and evidence output.
The server's existing lifetime resource fields retain their original boundary.
Do not add or equate counters from these different windows.

Syscall-entry counts include attempts and do not themselves report returned
bytes, successful writes or partial-write progress. An application `async_write`
can make several underlying calls. The repeated equality with completed frames
is an observation of these low-backlog baseline runs, not a protocol guarantee.
In the burst run attachment missed some early setup writes, so syscall and
lifetime frame totals differ.

## Observations

CPU seconds below are the two per-thread perf task-clock measurements and the
separate loadgen lifetime user-plus-system total. Frames are server lifetime
complete frames, including setup, Welcome and BBO. All four have zero slow-client
closures, zero Matching output waits, and no missing/discarded business frames.
Peer EOF/read-error counters at ordinary client teardown remain in raw reports.

| Diagnostic | Measured requests completed | Gateway sendto calls | Written frames | Gateway CPU s | Matching CPU s | Loadgen CPU s |
|---|---:|---:|---:|---:|---:|---:|
| mixed 10k, run 1 | 100,001 / 100,001 | 701,795 | 701,795 | 2.653 | 0.891 | 2.284 |
| mixed 10k, run 2 | 100,001 / 100,001 | 701,793 | 701,793 | 2.657 | 0.910 | 2.261 |
| mixed 45k | 450,001 / 450,001 | 3,151,699 | 3,151,699 | 8.584 | 1.901 | 7.359 |
| burst 2k | 20,001 / 20,001 | 138,538 | 138,767 | 0.606 | 0.121 | 0.549 |

No sendmsg/write/writev calls were counted in these attachment windows. The two
10k runs used identical planned bytes; their actual cross-client admission
orders and BBO/trade routing can differ, and each actual trace is checked.
At 45k the Gateway consumes a substantial fraction of the approximately
10.4-second attached interval; loadgen also uses substantial CPU. Neither fact
establishes a maximum sustainable rate or excludes transient client-side limits.

The following figures describe profiler-affected runs only:

| Diagnostic | RTT p99 us | Send-lag p99 us | Gateway-wait p99 us | Send high-water bytes | Command/event high-water |
|---|---:|---:|---:|---:|---:|
| mixed 10k, run 1 | 98.045 | 29.565 | 0.250 | 1,474 | 3 / 15 |
| mixed 10k, run 2 | 121.880 | 39.723 | 0.250 | 8,472 | 38 / 91 |
| mixed 45k | 174.551 | 40.827 | 4.042 | 5,938 | 31 / 121 |
| burst 2k | 3,923.296 | 5,050.056 | 19.126 | 21,676 | 62 / 231 |

The burst still has substantial planned-send lag. Its approximately 0.55 seconds
of loadgen lifetime CPU does not show that every individual burst was delivered
on schedule, nor prove that server changes will remove this lag.

Sampling retained 2,541 / 2,543 / 8,141 / 580 samples respectively, with zero
reported loss. Available call chains show socket send/TCP receive-wakeup paths
through `Connection::write`, as well as futex wakeups reached through
`MatchingPipeline::try_pop` and `try_submit`. For example, `try_to_wake_up` is
10.98% and 8.48% of combined sampled CPU in the first mixed and 45k runs.
Those shares include both processes and all sampled threads; they are not
percentages of request latency or independent additive bottleneck estimates.
They also show why locks/wakeup coordination cannot be declared irrelevant.
No off-CPU-duration or cache/IPC conclusion is inferred from these samples.

## Decision supported by this evidence

Test one bounded gather-write change: at most sixteen already queued frames and
4 KiB per operation, without waiting to fill a batch or changing the existing
send-byte limit. The syscall counts, distinct Gateway CPU and observed finite
backlogs make that a concrete hypothesis. The candidate must retain message
order, partial-write/close ownership and conservative M2 frame accounting.
Formal paired runs must establish whether fewer operations improve resource use
or latency without creating losses or unacceptable regressions.

Keep waiting/notification, mature SPSC and the order book unchanged for this
experiment. The profiles contain visible futex work but do not require a second
simultaneous optimization. There is no new evidence here attributing cost to
order-node allocation; the optional storage experiment remains unselected.

## Raw evidence and reproduction

`build/m3-diagnostics/` contains the executed helper, actual host metadata,
baseline fetch/build and tool-probe logs, and `baseline-run-1/`. Its four case
directories each retain the source/effective manifest, one warmup, one diagnosed
run, raw inputs and samples, actual admissions, snapshots, Reference results,
all profiler commands/PIDs/exit codes, `perf.data`, rendered call chains and
per-thread stat output. The helper is an experiment artifact rather than a
production observability subsystem.

All eight profiler processes were explicitly interrupted after loadgen finished
and before server drain, with successful recorded SIGINT requests. Seven actual
exits are `-2`; the second mixed run's `perf stat` exited zero. Both stat output
and perf reports decoded successfully. Raw exits were not rewritten. No loadgen
or server failed and no attempt was
discarded. The first evidence-copy attempt could not read root-owned perf files;
ownership of those four generated files was corrected and copying completed.
This did not rerun a measurement or modify raw file contents.

`baseline-files.json` records the guest SHA-256 and size of **203 original files,
308,807,236 bytes**. Host verification checked every file before preserving
`guest-report.*` and rerunning the independent summarizer. `host-verification.json`
records all four equal regenerated reports. `summarize_diagnostics.py` derives
the compact `diagnostic-summary.json` without editing raw evidence.

On a permitted Linux host, with the fixed clean baseline checkout and matching
Release build, the archived helper can reproduce fresh diagnostic directories:

```sh
python3 /path/to/evidence/profile_baseline.py \
  --repository /path/to/clean-m2-baseline \
  --output-dir /path/to/new-diagnostics \
  --host-environment /path/to/actual-host-environment.json
```

The helper needs passwordless permitted perf invocation, syscall tracepoints and
permission to signal only its own profiler process groups. A different host must
provide its actual environment. The M3 release evidence index will map these
local paths into permanent attachments; this diagnostic document alone is not
a claim of completed M3 formal measurement, CI or release acceptance.
