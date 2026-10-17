# M2 Linux service profiling

One representative mixed four-client workload was profiled separately from the
formal timing matrix. The retained second attempt provides 683 user-mode CPU
samples with zero reported lost samples, software counters, and a successful
independent reference check. The visible sample concentrations include socket
send/receive, Gateway scheduling, condition-variable/mutex operations and the
Matching worker. This is a coarse sampled view of this VM run, not a precise
breakdown of request latency or a hardware-counter result.

## Source, machine and workload

| Item | Recorded value |
|---|---|
| Source | `85de7f3262bc96a8ff889226592282cee1c57684`; checkout clean before and after |
| Server SHA-256 | `2348899014ba8415c1b4f6212541fb9ef61c6c5644af8631ae1a56a2812c4c23`; unchanged after execution |
| Server ELF build ID | `09fe9aa241ea3ac25e3be127c25a48c8846d11d9` |
| Build | GCC 13.3.0, C++20, Release `-O3 -DNDEBUG`, no sanitizer |
| Guest | Ubuntu 24.04 arm64, Linux `6.8.0-142-generic`, four visible CPUs, 4 GiB assigned RAM |
| Virtualization | QEMU/HVF guest on macOS; loopback traffic within the guest; no exclusive physical core or frequency control |
| Profiler | Linux perf 6.8.12, invoked with sudo because unprivileged software counters are restricted |
| Workload | Four clients; mixed; C=1,000; 500 setup orders; seed 20261016; 10,000 planned requests/s |
| Finite plan | 100,001 measured requests, final scheduled offset 10 seconds; independent 130-request warmup |
| Bounds | Command/event queues 1,024 each; server/client send limits 65,536 bytes; client in-flight limit 16,384; drain/shutdown deadlines 5 seconds |
| Execution | Independent Codex subagent `/root/reference_model`; second attachment began `2026-10-16T23:31:06Z` |

The warmup used a separate server instance. Profiling attached after the measured
server's READY message, when Gateway and Matching already existed. It included
setup and the measured workload. After loadgen exited, the helper explicitly
interrupted both profilers before requesting normal server drain. A 15-second
sleep in each profiler invocation bounded the attachment independently. Attachment
is not synchronized to the first measured request, so these counters do not have
exactly the same window as the client's latency samples.

The instrumented run completed all 100,001 planned requests with no business
rejections, not-started requests, failed requests or unfinished requests. The
server admitted and completed 100,501 commands including setup; all published
business events were consumed, and no business frames were missing or discarded.
Reference verification passed for the actual admission trace and final book.
The independent summary validated both warmup and measurement attempts. Its
latency/throughput output is retained for consistency checking and is excluded
from the formal timing conclusions.

## Sampling and software counters

The actual record command used `perf record -e cpu-clock:u -F 999
--call-graph dwarf,8192 -p <server_pid> -- sleep 15`, writing `perf.data`.
Concurrent `perf stat` attached to the same process with
`task-clock,context-switches,cpu-migrations,page-faults`. The target was the
server process and its two threads; the load generator and reference verifier
were separate processes. Saved command arrays include the exact PID and paths.

`perf report --stdio --header --no-children --sort comm,dso,symbol
--percent-limit 0.5` decoded the data successfully. It reports 683 samples, zero
lost samples, and a first-to-last sample span of 9,960.830 ms. Selected leading
self-sample entries are below; call-chain child percentages are not added to
these percentages.

| Symbol | User CPU sample share |
|---|---:|
| libc `__send` | 8.49% |
| `llmatch::MatchingPipeline::run()` | 7.32% |
| libc `pthread_cond_signal` | 6.15% |
| libc `epoll_pwait` | 4.54% |
| Unresolved libc address `0x820b8` | 4.25% |
| libc `pthread_mutex_lock` | 3.81% |
| libc `recv` | 3.81% |
| Asio `scheduler::do_run_one` | 2.93% |

The `__send` call chain leads through `Connection::write`, `route` and `pump` in
[server.cpp](../src/server.cpp). The worker sample maps to
[MatchingPipeline::run](../src/pipeline.cpp), which advances the engine, publishes
messages and records completion evidence. Signaling and locking samples are
consistent with the implemented condition-variable wait and Gateway notification
paths. Optimized/inlined work can be charged to a caller, so the worker's 7.32%
is not a standalone measurement of the order-book algorithm. Unresolved libc
addresses remain unattributed.

| Software counter | Observed value |
|---|---:|
| task-clock | 3,469.77 ms |
| context switches | 422,671 |
| CPU migrations | 38 |
| page faults | 3,233 |
| perf-stat elapsed window | 10.133115317 s |

The server's separate lifetime resource report records 0.810952 s user CPU and
3.509142 s system CPU, measured before evidence formatting. That lifetime includes
startup and shutdown and differs from the attachment window. User-only samples
exclude kernel execution and time spent asleep; the table cannot assign the
system CPU time or blocked wall time to individual functions. Hardware cycles,
instructions and cache misses were unavailable in this VM, as retained probes
show. No IPC, cache-efficiency or hardware-cycle claim is made from the empty
hardware columns printed by perf.

Sampling and the simultaneous stat process add overhead. The run has only one
retained completed profiling attempt at the final sampling frequency and hundreds,
not millions, of samples. Frequency/affinity were not controlled, and the guest
shares its physical host. The percentages describe broad observed paths; they
are not repeatability estimates or optimization recommendations.

## Evidence and both attempts

Local evidence is under `build/m2-profiling/`. `index.json` hashes the archive,
helper, assessment, probes and primary perf files. The raw archive
`raw-profile-attempts.tar.gz` is 19,023,783 bytes with SHA-256
`8352625ba1914e1e54d1989aaa610afe0ed5f132d90ed9b23a85d65df4d3cbc3`.
It preserves both run directories, each containing inputs, manifests, client and
server samples/reports, reference results, the executed helper, profiler command
arrays, raw `perf.data`, rendered report, build IDs, stat output and stderr.

Attempt 1 used 99 Hz and recorded 74 samples with no reported loss. Its temporary
helper wrote the manifest terminal state after invoking the summary, so the
summary correctly rejected it. Server shutdown also ended perf record with
SIGTERM (`-15`). All its material remains; it is not used for the table above.

Attempt 2 fixed the manifest ordering and explicitly stopped perf before server
shutdown. The service, reference check, summary, stat and perf report succeeded.
Perf record finalized the data after the requested SIGINT and returned `-2`.
The executed wrapper still returned 1 because its final condition accepted only
zero profiler exits. `assessment.json` preserves that fact and separately checks
the requested signal, successful data decoding, zero lost samples, successful
service/reference/summary and unchanged clean source/binary. The standalone
helper was then corrected to recognize this specific requested SIGINT outcome;
the original executed copies and raw exits were not rewritten, and no third
measurement was performed to hide the earlier attempts.

The helper and probes outside the raw archive are included in the surrounding
evidence directory. To repeat the bounded procedure on a permitted Linux host,
use the archived helper with a fresh output directory:

```sh
python3 /path/to/evidence/profile_service.py --repository "$PWD" \
  --output-dir "$PWD/build/profile-new"
```

It reuses the project's generator, service runner and independent summary;
it does not alter production code or build flags. The final evidence package
must retain the helper/index alongside the raw archive. The
[M2 acceptance record](m2_acceptance.md) separately tracks final-source CI,
formal measurements and publication.
