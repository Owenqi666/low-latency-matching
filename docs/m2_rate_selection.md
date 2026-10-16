# M2 formal rate selection

Rates were frozen before formal measurement, using two finite calibration batches on
clean source `85de7f3262bc96a8ff889226592282cee1c57684`. These are exploratory
capacity observations, not the five-round formal results. No production code or
capacity was tuned between probes.

## Environment and retained attempts

Ubuntu 24.04.5 arm64, kernel 6.8.0-142, GCC 13.3.0, unsanitized Release;
QEMU 11.1.2/HVF on macOS 26.6.2, Apple M5 Pro (18 host cores, 48 GiB).
The guest has 4 vCPUs and 4 GiB. Server and loadgen share guest TCP loopback.
No affinity, frequency or turbo control; no concurrent guest build/test during probes.
This measures the entire service/loadgen/VM path, not an isolated matching-core limit.

Both batches preserve their source/effective manifests, input schedules, all warmups,
all measured attempts, logs, server/client samples and reference results. Independent
summaries accepted all 30 attempts as internally consistent. Some attempts failed to
deliver all requests; those failures are included below and remain in the archive.

| Batch / row | Target / s | Completed / planned | Slow-peer closes | RTT p99 (us, completed only) |
|---|---:|---:|---:|---:|
| ladder / mixed_4_r5000 | 5000 | 10001 / 10001 | 0 | 108.207 |
| ladder / mixed_4_r10000 | 10000 | 20001 / 20001 | 0 | 93.749 |
| ladder / mixed_4_r20000 | 20000 | 40001 / 40001 | 0 | 113.457 |
| ladder / mixed_4_r40000 | 40000 | 80001 / 80001 | 0 | 150.540 |
| ladder / mixed_4_r80000 | 80000 | 16 / 160001 | 4 | 1056.238 |
| ladder / mixed_4_r160000 | 160000 | 19 / 320001 | 4 | 1041.946 |
| refine / mixed_4_r45000 | 45000 | 135001 / 135001 | 0 | 181.081 |
| refine / mixed_4_r50000 | 50000 | 150001 / 150001 | 0 | 200.206 |
| refine / mixed_4_r60000 | 60000 | 13 / 180001 | 4 | 952.530 |
| refine / burst_4_r2000 | 2000 | 10000 / 10000 | 0 | 4605.651 |
| refine / burst_4_r5000 | 5000 | 4589 / 15001 | 4 | 8935.556 |
| refine / burst_4_r10000 | 10000 | 463 / 30001 | 4 | 4032.950 |
| refine / cancel_heavy_4 | 10000 | 30001 / 30001 | 0 | 84.332 |
| refine / sweep_4 | 10000 | 30001 / 30001 | 0 | 204.290 |
| refine / mixed_1 | 10000 | 30001 / 30001 | 0 | 81.583 |

The mixed 50,000/s probe completed every request over three seconds; 60,000/s
and higher probes exposed bounded output backlog and explicit slow-peer closure.
The 2,000/s burst probe completed all requests; 5,000/s and 10,000/s burst
probes lost requests. A burst packs each 100 ms of planned arrivals into 10 ms.
Low completed-only percentiles on failed attempts do not imply good overload latency.

## Frozen matrix

| Row | Target / s | Planned requests per measured round | Planned span |
|---|---:|---:|---:|
| mixed_4 | 10000 | 100001 | about 10.00 s |
| cancel_heavy_4 | 10000 | 100001 | about 10.00 s |
| sweep_4 | 10000 | 100001 | about 10.00 s |
| burst_4 | 2000 | 100000 | about 49.91 s |
| mixed_1 | 10000 | 100001 | about 10.00 s |
| mixed_4_near | 45000 | 450001 | about 10.00 s |
| mixed_4_overload | 80000 | 800001 | about 10.00 s |

Each row has one independent 1,000-command warmup and five fresh measured
server instances. The ordinary one-client and four-client mixed rows use the
same aggregate rate. The burst rate differs to keep its bounded 10x peak within
the observed loss-free region. Near capacity is fixed at 45,000/s, 90% of the
highest loss-free short mixed rate, rather than assuming three seconds proves
long-run stability. Overload is fixed at 80,000/s. All limits retain task defaults.

Formal outcomes may still fail or have insufficient completed samples. Retain
them without changing these parameters or hiding failed attempts. The experiment
has a finite plan and five-second client/server drain deadlines. The report must
separate successful delivery, internal drain and evidence validity.

Inputs: [locked manifest](../data/workloads/service-formal.json). Raw batch roots
in the long-term evidence archive are `measurement/m2-calibration-ladder/` and
`measurement/m2-calibration-refine/`; their binary hashes and environment records
are in each `manifest.json`. See [measurement method](service_benchmark_method.md).
