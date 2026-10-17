# M2 Linux synchronous core measurements

Commit `f58ff79d49fd08c2bcb399ad989eb47ed0830a40` completed four existing
workloads at capacity 1000, with 100000 commands and five rounds per timing
mode. All 40 rounds passed the benchmark's reference, count, checksum and final
snapshot checks. The results contain 2000000 individual latency samples and
4000000 timed commands across both modes. Independent summarization passed in
the guest and again after copying the evidence to the host.

This measures the synchronous matching core. It supplies the third M2 timing
boundary alongside service and network measurements; it does not measure their
queues, Gateway, socket I/O or BBO publication. These Linux VM results are not a
performance ranking against the earlier M1 platform.

## Source, build and environment

Executor: Codex subagent `/root/baseline_core`. The existing clean Linux checkout
at `/home/m2/llmatch-clean-ce9e94f` was fetched and moved from
`85de7f3262bc96a8ff889226592282cee1c57684` to the commit above. Recorded Git status
was empty before and after measurement. Release configuration and an incremental
build reused its dependencies; only the pipeline and server lifecycle test
targets rebuilt. This is a follow-up to the
[clean checkout reproduction](m2_clean_checkout.md), not another first-install run.

SHA-256 before and after the update was identical for `matching_server`,
`loadgen`, `verify_service`, `bench_core` and `clock_probe`. The transition
evidence retains all five comparisons. The two measurement executable hashes are:

```text
f165ba00ea9a1e266bd1b27efa1a5116512a1a60ba6aa92b40d87baba1400780  bench_core
1d42927749703e2d4471d3c3d64793f62d6f64c12f9c12b853010998d5be89ec  clock_probe
```

The affected Release groups passed 14/14 CTest entries in 1.66 seconds: nine
Pipeline tests, two ServerLifecycle tests and the three Python entries
`service_integration`, `service_evidence`, and `service_benchmark`. Discovery and
JUnit checks confirmed that every selected entry executed without a skip. This
was targeted follow-up verification, not a new full-suite or remote CI run.

| Property | Recorded value |
|---|---|
| Guest | Ubuntu 24.04.5 LTS; aarch64; Linux 6.8.0-142-generic; glibc 2.39 |
| Host context | macOS 26.6.2 (25G83), Apple M5 Pro, 18 cores, 48 GiB RAM |
| Virtualization | QEMU 11.1.2 with HVF; 4 guest vCPUs, 4096 MiB assigned RAM |
| Compiler/build | GCC 13.3.0; C++20; Release `-O3 -DNDEBUG`; sanitizers OFF |
| Tools | CMake 3.28.3; Python 3.12.3 |
| Core execution | One matching thread; separate latency and throughput rounds |
| Scheduling | Not pinned; inherited affinity CPUs 0–3; no exclusive core |
| Frequency controls | Frequency and turbo not controlled; governor unavailable |
| Background | Host OS and Codex active; no other VM build/test/profile/network measurement in this window |
| Observed one-minute guest load | 0.035–0.250 at the four runner captures |

The guest operation window was 2026-10-16 23:34:07–23:34:37 UTC. It includes
generation, verification, warmup, timing, file output and summary generation;
the 30-second window is not a core timing result. Runtime manifests record
source commit, clean status, source and binary hashes, compiler flags, environment
and individual capture times. The prepared plan identifies an earlier planning
revision; the runtime provenance binds the executed results to `f58ff79`.

## Workloads and measurement boundary

The four manifests retain generator `m1-workloads-v1`, its original fixed seeds
and algorithm. Their capacity list was restricted to `[1000]`; each uses working
depth 64 and 500 setup orders. Generated config, setup and input hashes match
the corresponding existing workload inputs recorded in the prepared plan.

Counts below describe one 100000-command input, excluding setup. Every timed
round uses those same bytes and reproduces these counts.

| Scenario | Seed | Limit / market / cancel | Accepted / rejected | Trades | Events | Live orders: initial → final; observed range |
|---|---:|---|---|---:|---:|---|
| mixed | 20261016 | 50000 / 16667 / 33333 | 100000 / 0 | 33334 | 300000 | 500 → 500; 500–501 |
| cancel_heavy | 20261017 | 48780 / 0 / 51220 | 97561 / 2439 | 0 | 297561 | 500 → 499; 499–500 |
| sweep | 20261018 | 98462 / 1538 / 0 | 100000 / 0 | 98432 | 396894 | 500 → 530; 500–564 |
| clustered | 20261019 | 65984 / 1031 / 32985 | 100000 / 0 | 32992 | 331961 | 500 → 507; 500–564 |

The 2439 `cancel_heavy` rejections are deliberate `UnknownOrder` cancellations.
The sweep workload reaches 64 trades across eight levels in one command;
clustered reaches 32 trades across four levels. Background setup orders mostly
remain passive: capacity 1000 is not a claim of full-capacity pressure. The
scenario names describe command patterns, not network arrival processes, and
the sweep throughput includes the replenishing limit commands.

The existing [core benchmark method](benchmark_method.md) is unchanged. Before
timing, the production and independent reference engines compare complete
ordered events for every command and canonical setup/final snapshots. A separate
engine warms up on the same input. Each mode and round then starts with a fresh
engine and identical setup outside timing.

- Latency encloses one `process` call, including matching, map/list allocation
  and output generation. Status checks, event consumption, sample recording,
  parsing, reference execution and file I/O are outside that interval.
- Throughput encloses the full input loop, including process status checks,
  counters and consumption of every output event field into a checksum. It has
  no per-command clock read. Those harness costs are retained.

The preallocated output span contains `C+4 = 1004` events at 144 bytes each
(144576 bytes). After each timed mode, totals, full-event checksum, invariants
and final snapshot must match the verified replay. The checksum checks measured
round consistency; it does not replace the full event comparison before timing.
Service and RTT boundaries are specified separately in
[the service benchmark method](service_benchmark_method.md).

## Observed results and limits

Each cell below is the minimum–maximum across all five rounds of its mode,
with a single value when unchanged. Rates are millions per second. These ranges
retain all rounds and are not confidence intervals.

| Scenario | Core p50 (ns) | Core p99 (ns) | Completed commands/s (M) | Accepted commands/s (M) | Trades/s (M) |
|---|---:|---:|---:|---:|---:|
| mixed | 42 | 84 | 13.068–13.188 | 13.068–13.188 | 4.356–4.396 |
| cancel_heavy | 42 | 84 | 12.372–13.233 | 12.070–12.911 | 0 |
| sweep | 42 | 1125–1291 | 8.588–8.678 | 8.588–8.678 | 8.454–8.542 |
| clustered | 42 | 542–583 | 10.829–11.142 | 10.829–11.142 | 3.573–3.676 |

Each overall latency round has 100000 samples and meets the existing p99 sample
count threshold. Its per-command-kind/outcome groups have fewer samples and are
marked below that threshold in the raw report. Meeting the threshold alone
does not establish tail stability. No p99.9 result is claimed.

All four clock probes observed a minimum positive interval of 41 ns,
back-to-back p50 of 0 ns and p99 of 42 ns, with 66963–67370 zero intervals out of
100000 pairs. Mean time for two reads plus duration recording was 28.16–28.70 ns;
the separate one-read-plus-timestamp-store experiment measured 14.27–15.36 ns.
The nominal 1 ns clock period is a representation property. The 42 ns matching
p50 lies near the observed clock step and should not be interpreted as precise
instruction cost. No clock constant is subtracted from samples; batch throughput
provides a separate observation with fewer clock boundaries.

Peak process RSS was 28.625 MiB (mixed), 29.000 MiB (cancel_heavy), 30.449 MiB
(sweep), and 29.195 MiB (clustered). This includes parsed inputs, reference work,
warmup and earlier rounds, so it is not isolated order-book memory. CPU deltas
likewise cover the full mode loop and harness. The VM, uncontrolled scheduling
and frequency, and short operation durations limit conclusions beyond this
recorded environment. No bare-metal result, platform-independent speedup or
network latency is inferred.

## Reproduction and evidence index

From the recorded clean guest checkout, the principal commands were:

```sh
git fetch origin f58ff79d49fd08c2bcb399ad989eb47ed0830a40
git checkout --detach f58ff79d49fd08c2bcb399ad989eb47ed0830a40
cmake --preset release
cmake --build --preset release --parallel 2
ctest --preset release -L 'concurrency|service' --output-on-failure --no-tests=error
for scenario in mixed cancel_heavy sweep clustered; do
  python3 scripts/run_bench.py --binary build/release/bench_core \
    --manifest "build/m2-measurement/core-manifests/$scenario.manifest" \
    --repeats 5 --output-dir build/m2-measurement/core-run-1
done
python3 scripts/summarize_bench.py build/m2-measurement/core-run-1
```

CTest ran serially; its discovery, JUnit and group-check outputs are retained.
The measurement output directory was fresh. All four first attempts succeeded;
there were no failed or selectively discarded rounds. Reproduction should use
another fresh result directory to preserve this evidence.

The guest summary reported `validated 4 workload/capacity runs`. After download,
the independent summarizer validated all four again. The regenerated report
matches the preserved guest report apart from absolute directory paths. The
reused tool's report title still says “M1 core benchmark report”; the runtime
commit and manifests above identify this M2 execution.

| Local path, relative to repository root | Contents |
|---|---|
| `build/m2-measurement/core-f58ff79-transition/` | Source transition, clean status, five binary hash comparisons, configure/build logs, discovery, JUnit, 14-test results and service artifacts |
| `build/m2-measurement/core-manifests/` | Four manifests, prepared plan, command list and source file list |
| `build/m2-measurement/core-run-1/provenance/` | Actual source/binary hashes, commit/status, CMake cache and compile commands, environment, timestamps, runner logs, prepared-plan copy and independent summary logs |
| `build/m2-measurement/core-run-1/<scenario>/capacity_1000/` | Config/setup/input, hashes, run manifest, clock probe, verification rows, five latency CSVs, all ten final snapshots and per-run summary |
| `build/m2-measurement/core-run-1/report.json` and `report.md` | Downloaded evidence revalidated by the independent summarizer |
| `build/m2-measurement/core-run-1/provenance/guest-report.*` | Original guest reports preserved before local revalidation |

The approximately 55 MiB raw result set was copied back to the host before
returning the VM, which had 4.4 GiB disk space free. These ignored local paths
are an evidence index, not a public archive URL. Final publication and PR/main
acceptance remain tracked in [M2 acceptance](m2_acceptance.md).
