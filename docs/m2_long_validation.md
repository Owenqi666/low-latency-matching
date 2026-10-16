# M2 service validation with 120,000 workload commands

On 2026-10-16 from 23:13:09 to 23:13:36 UTC, a fixed-seed service run completed
120,000 workload commands across mixed, cancel-heavy and sweep scenarios. The
actual admitted order, per-command business-event digests and final books
passed independent Reference replay. This is correctness evidence for T07,
including output congestion with an event queue of capacity 1. It is not a
formal performance result or a Linux execution claim.

## Source and execution conditions

The saved runner manifest records clean commit
`ce9e94f134f6d9894f67922586004c7650a32467`, macOS 26.6.2 / Darwin 25.6.0, arm64,
18 reported logical CPUs and 51,539,607,552 bytes of system memory. Server,
loadgen and verifier were Debug builds using Apple Clang 21.0.0
(`clang-2100.1.1.101`), `-g -std=c++20`, without sanitizers. Python was 3.14.8.
The manifest also preserves an unused Release flags cache entry; that does not
make these binaries Release builds.

The server ran one Gateway and one Matching thread, with loadgen in a separate
process over same-host TCP loopback. Affinity, frequency and turbo were not
controlled; no exclusive core was claimed. The runner recorded background load
and hardware observations. The retained manifest identifies the runner and
binaries but does not record an operator identity. This document was checked
against saved files by subagent `/root/baseline_core` without rerunning the
experiment.

| Executable | Recorded SHA256 |
|---|---|
| `build/debug/matching_server` | `c467fa0dec849a4672b8b91bbce968fc704c62d8563a4c67cc25a75180e2ca3f` |
| `build/debug/loadgen` | `50ccf540a4bc08095abb450e638d387bf275cf56241e9f08ba16286d62d8acaa` |
| `build/debug/verify_service` | `a474d787d6f9da1ee299e5ae90c9e758b441efc18a82e5f1f6dbdaf2cf169fdc` |

## Plan and results

Generator `m2-service-workloads-v1` used base seed 20261016, capacity 1,000,
500 background setup orders, working depth 64 and four connections per row.
Each row had one independent 130-command warmup and one 40,000-command workload
at a planned 5,000 commands/s. Command/event queue capacities were 2/1; the
server's measurement-run record limit was exactly 40,500, including setup.
Client in-flight capacity was 16,384, client/server send bounds were 65,536
bytes, and client drain/server shutdown deadlines were 5,000 ms.

| Workload | Seed | Workload Complete | Business accepted / rejected | Admitted including setup | Business events including setup | Trades | Output waits |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mixed | 20261016 | 40,000 | 40,000 / 0 | 40,500 | 121,500 | 16,000 | 108,895 |
| Cancel-heavy | 20361019 | 40,000 | 39,025 / 975 | 40,500 | 120,525 | 0 | 78,050 |
| Sweep | 20461022 | 40,000 | 40,000 / 0 | 40,500 | 160,245 | 39,360 | 117,055 |

Thus the long workload contains **120,000** started and completed commands,
with 119,025 business acceptances and 975 business rejections. None was
unstarted, failed or unfinished. Setup adds 1,500 commands to the three main
service traces; separate warmups and their setups add another 1,890. Reference
verification therefore covers 123,390 admitted commands across all six runs,
while the stated 120,000-command long-test size excludes setup and warmup.

Every server exited 0, drained all admissions, ended idle with no current
command, and matched published/consumed business-event and BBO counts. No
missing business recipient or discarded frame was reported. Event high-water
was 1 in each main run; command high-water was 1, 2 and 2 respectively. The
recorded output waits show repeated output-space contention; these observations
do not assert that arbitrary scheduler interleavings have been proven correct.

`summary-check.log` records `Validated 6 declared attempts; all succeeded: True`.
The independent summary validates all declared runs rather than silently
dropping missing attempts. Each main `verification.json` reports 40,500
commands passed, and binds the actual trace, final snapshot, sample CSV,
server report and engine configuration with hashes.

## Commands and retained records

The runner inputs and per-process argument arrays are retained. The equivalent
top-level invocation is shown below; it is a reproduction command derived from
those records, not a separately saved shell transcript. A rerun must use a new
output directory because the runner refuses to overwrite existing evidence.

```sh
python3 scripts/run_service_bench.py --server build/debug/matching_server \
  --loadgen build/debug/loadgen --verifier build/debug/verify_service \
  --manifest build/m2-long-service/long-manifest.json \
  --output-dir build/m2-long-service/run-2
python3 scripts/summarize_service_bench.py build/m2-long-service/run-2
```

The original output is `build/m2-long-service/run-1/`. Its source workload
manifest has SHA256
`fdefde2c0d5a6f9b1e081a0b320d406588369ec8439007e4f709952b1791c9e6`;
the completed run manifest has SHA256
`3b50576fe57e6a1c405f475dc0ca37b96d2b089e926421f6f4f4a2319f2a4723`.
The latter records source state, binary hashes, compiler flags, environment,
derived per-row seeds, all six expected attempts and summary exit status 0.

| Evidence path, relative to `build/m2-long-service/` | Contents |
|---|---|
| `long-manifest.json`, `run-1/source_manifest.json` | Fixed workload settings and correctness-only purpose |
| `run-1.log`, `run-1/manifest.json` | All attempt starts/completions; source, environment, binaries and expected runs |
| `run-1/report.json`, `run-1/report.md`, `run-1/summary-check.log` | Complete counts, saved descriptive timings and successful independent summary |
| `run-1/runs/<row>/<warmup or round_1>/run.json` | Exact server/loadgen/verifier argument arrays, setup count, input hashes, exits and replay result |
| Each run's `inputs/` | Engine config, setup/input trace, sending schedule and workload metadata |
| Each run's `client/` | Logical-to-actual ClientId mapping, counts, raw workload/setup samples and client clock probe |
| Each run's `server/` | Actual admitted trace, per-command samples/digests, final snapshot, counters and `verification.json` |
| Each run's `logs/` | Server READY/stdout/stderr, loadgen output and Reference verification log |

These ignored local paths must be included in the final long-term evidence
archive; they are not public artifact download links.

## Validation boundary

The long run compares ordered per-command FNV-1a business-event digests, event
and trade counts, completion status and the canonical final book against the
independent Reference Engine. Digest equality is not a collision-free
full-event proof. It does not independently compare every client-visible BBO
or route byte in this long run. The separate small
`service_evidence` test compares complete routed events and BBOs for 18 commands
across three clients, and the [Linux reproduction](m2_clean_checkout.md)
records its execution alongside the long-run evidence.

The saved manifest uses runner mode `calibration` to permit these short
correctness experiments, with an explicit correctness-only rate-selection
description. It is not a calibration of the final Linux benchmark rate. Each
main row has one roughly eight-second plan and 40,000 workload samples;
`normal_sample_target_met` is false. There are no five-round formal results or
profiling conclusions here. Saved latency numbers remain diagnostic raw data
and must not be presented as M2's formal Linux p99, throughput limit or a speedup
over M1. Later source revisions require their own validation evidence.
