# M3 experiment plan

Status: baseline verified; targeted diagnosis in progress. No performance result
or candidate adoption is claimed. The experiment decision and parameters below
will be frozen before candidate implementation and formal measurement.

## Baseline and scope

The baseline is the published `m2-service` commit
`db9b74f4181a2dc4a50966c20080949c839bf73f`. At M3 start, the local main, fetched
`origin/main` and fetched tag all resolve to that commit. The GitHub release is
published and its five asset hashes match the M2 publication record. The only
pre-existing tracked modification adds the local M3 task book to `.gitignore`;
it is preserved. Work continues on `feat/m3-experiments`.

M3 must complete one evidence-backed experiment, not necessarily achieve a
speedup. A second order-slot experiment is conditional on separate diagnostic
evidence and is not required for delivery. The matching algorithm, two production
threads, Boost SPSC queues, protocol, limits and Reference implementation remain
the baseline contracts.

M2's old results motivate a hypothesis but are not the new A/B control. All five
80,000/s overload attempts reached the per-connection outbound limit while
Matching recorded no output-space waits. The old user-only profile did not
attribute kernel or blocked time and used the earlier loadgen. Neither result
establishes that allocation, locking or socket writes are the dominant cause.

## Targeted diagnosis

Use a clean M2 source and the corrected load generator in the existing Linux
VM. Record the new running kernel and environment after restarting that VM.
Run bounded mixed-four-client diagnostics at 10,000/s twice, 45,000/s once,
and a temporal-burst diagnostic. Preserve actual input, admission replay,
resource observations, profiler commands and exits for every attempt.

Distinguish Gateway, Matching and loadgen CPU/scheduling observations. Examine
write/send calls or call chains, outbound backlog, request send lag and loss.
Unavailable hardware/kernel events remain unavailable rather than zero.
Profiler-assisted timings are excluded from the formal comparison.

The first candidate is bounded gather-write of existing queued frames. This
would change how many frames one Asio composed write carries; it would not wait
for a batch to fill. Diagnosis must support this as a useful experiment before
implementation. A single waiting-coordination experiment may replace it if the
new evidence points there; both mechanisms will not change together.

## Formal comparison

Preserve the seven rows of `data/workloads/service-formal.json`, with five
measured runs per variant per row and separate warmups: 70 measured runs plus
14 warmups. Use the same Linux Release toolchain, inputs, corrected loadgen,
verifier, capacities and recording settings. Start a fresh server each time.
Within each row, use AB for odd rounds and BA for even rounds; warmups are A then
B. Never run A and B concurrently.

Each variant retains a complete manifest, validated by the existing independent
service summary. A thin paired runner reuses the existing per-run executor;
the paired checker additionally binds inputs, versions and execution order.
Record each binary's actual source checkout rather than the runner's checkout.
If observational changes are needed, apply them equally to both variants and
preserve that source difference from the unmodified M2 tag.

Before measurement, freeze candidate constants, primary metric, expected
tradeoffs and adoption criteria after the diagnosis. Preserve unsuccessful
runs and all raw outcomes. Comparison will distinguish evidence validity,
server drain, client delivery and sufficient latency samples.

## Completion and publication

Reuse the M2 failure/recovery evidence and existing tests. Add only tests of the
new mechanism and paired-evidence checks. Keep Debug, Release, ASan/UBSan and
independent TSan CI, core/network smoke and artifact inspection. A clean Linux
reproduction, latest PR checks, normal merge, exact-main push checks, durable
archives and verified `m3-experiments` publication remain required even if the
candidate is rejected. Original planning documents and VM/SSH files remain local.
