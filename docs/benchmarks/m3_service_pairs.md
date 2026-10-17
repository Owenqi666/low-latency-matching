# M3 service pairs: all 35 formal pairs

These tables derive from the preserved independent guest summaries in
`build/m3-measurement/host-revalidation/guest-derived/`. Original copied-file
SHA-256 validation passed for 1,618 files. Independent host recomputation of all
raw samples exited 0, with all eight derived files byte-identical to the guest
results (`build/m3-measurement/host-revalidation/verification.json`). The
[experiment report](../m3_report.md) states the
source/environment, frozen rule, negative decision and remaining acceptance.
The [complete JSON](m3_service_pairs.json) retains all precision, per-run
observations, resource records, input hashes and source/tool provenance.

A is observed one-frame control `7b8fcd3b074ed39ff24a3488253397e1dfb7094e`;
B is 16-frame candidate `b1ba98c205de3bd717eb0f118fb9771d1f251a25`.
A contains the same send-queue extraction, counters and descriptor storage as B;
it is not the original M2 binary. Both share one loadgen and verifier. All results
are unsanitized Linux Release on the same four-vCPU QEMU/HVF guest.

## Reading the tables

CPU/request is **server lifetime user + system CPU in microseconds**, including
setup and shutdown before evidence output, divided by the number of completed
measured requests received by the client. It is an amortized cost, not the CPU
window inside a request. RTT p99 is nearest rank for each run's completed-only
actual-write-to-Complete samples, in microseconds. Rates, other percentiles,
service/gateway/lag samples and full counters are available in the JSON.

`Δ` is `100 × (B/A − 1)` within that pair; scene summaries take the median of
those five values. A negative delta means a decrease. Ranges show the minimum
and maximum observed pair/run, not confidence intervals. Rounded display values
are not used to calculate deltas. `—` means a failed pair has no comparative
benefit delta; its absolute completed-subset observations are still shown.
The five failed pairs are not replaced, pooled or filtered from outcome reporting.

Each scene has a separate 1,000-command warmup on each side, excluded below.
All 14 warmups succeed. All 70 measured attempts meet the normal sample threshold
and all 84 attempts drain with valid Reference evidence. Delivery succeeds in
65/70 measured attempts, giving 30/35 fully delivered pairs. AB/BA is the actual
sequential execution order, never concurrent execution.

## Paired summaries

| Scene | Fully delivered pairs | CPU/request paired change, median [min, max] | CPU improvements | RTT p99 paired change, median [min, max] |
|---|---:|---:|---:|---:|
| mixed_4 | 5/5 | -8.14% [-15.69%, -4.23%] | 5/5 | -5.09% [-45.64%, +23.21%] |
| cancel_heavy_4 | 5/5 | -3.59% [-4.73%, +2.12%] | 4/5 | -4.96% [-27.40%, +5.32%] |
| sweep_4 | 5/5 | -6.71% [-8.89%, -5.78%] | 5/5 | -54.71% [-58.42%, -22.11%] |
| burst_4 | 5/5 | -34.37% [-45.83%, -23.83%] | 5/5 | -81.92% [-85.19%, -71.97%] |
| mixed_1 | 5/5 | -5.60% [-8.09%, -4.38%] | 5/5 | +71.30% [-5.47%, +101.38%] |
| mixed_4_near | 5/5 | -14.68% [-14.83%, -14.49%] | 5/5 | -30.93% [-36.14%, -14.06%] |
| mixed_4_overload | 0/5; A 0/5, B 5/5 | — | — | — |

The primary 45,000/s CPU rule passes, but `mixed_1` breaches the +10% median
RTT p99 limit. The 16-frame candidate is rejected and the production constant
has been restored to one frame. Overload's improved finite delivery is retained
without using incomplete A runs for speedup ratios.

## Every measured pair

All non-overload runs complete their full plan: 100,001 requests for ordinary
mixed/cancel/sweep/one-client, 100,000 for burst, and 450,001 at 45,000/s. Both
variants record zero failed, not-started and unfinished requests in those scenes.
The cancellation scene has 2,439 expected business rejections per run on both
sides; those requests still complete. Overload plans 800,001 per variant/run;
its distinct losses are tabulated below.

### mixed_4

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 40.931 | 38.377 | -6.24% | 89.041 | 85.416 | -4.07% | full/full |
| 2 | BA | 41.486 | 34.979 | -15.69% | 90.125 | 111.042 | +23.21% | full/full |
| 3 | AB | 40.657 | 38.935 | -4.23% | 109.751 | 90.751 | -17.31% | full/full |
| 4 | BA | 43.294 | 39.770 | -8.14% | 160.586 | 87.293 | -45.64% | full/full |
| 5 | AB | 41.508 | 37.956 | -8.56% | 94.876 | 90.043 | -5.09% | full/full |

### cancel_heavy_4

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 32.936 | 31.752 | -3.59% | 78.919 | 75.001 | -4.96% | full/full |
| 2 | BA | 33.378 | 32.168 | -3.63% | 77.294 | 76.126 | -1.51% | full/full |
| 3 | AB | 33.197 | 32.450 | -2.25% | 76.002 | 80.044 | +5.32% | full/full |
| 4 | BA | 31.425 | 32.091 | +2.12% | 111.462 | 80.919 | -27.40% | full/full |
| 5 | AB | 33.556 | 31.969 | -4.73% | 93.211 | 85.211 | -8.58% | full/full |

### sweep_4

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 35.117 | 32.762 | -6.71% | 217.590 | 98.545 | -54.71% | full/full |
| 2 | BA | 35.488 | 32.332 | -8.89% | 220.049 | 100.045 | -54.54% | full/full |
| 3 | AB | 36.406 | 34.165 | -6.15% | 215.258 | 167.672 | -22.11% | full/full |
| 4 | BA | 37.058 | 34.075 | -8.05% | 219.341 | 98.379 | -55.15% | full/full |
| 5 | AB | 36.226 | 34.131 | -5.78% | 220.549 | 91.712 | -58.42% | full/full |

### burst_4

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 38.258 | 20.724 | -45.83% | 5014.276 | 1405.390 | -71.97% | full/full |
| 2 | BA | 36.173 | 23.742 | -34.37% | 4923.770 | 1158.377 | -76.47% | full/full |
| 3 | AB | 33.488 | 20.871 | -37.68% | 4829.200 | 715.039 | -85.19% | full/full |
| 4 | BA | 27.638 | 21.051 | -23.83% | 3804.268 | 687.627 | -81.92% | full/full |
| 5 | AB | 33.096 | 22.811 | -31.08% | 4215.335 | 703.969 | -83.30% | full/full |

### mixed_1

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 33.608 | 31.724 | -5.60% | 81.293 | 127.293 | +56.59% | full/full |
| 2 | BA | 33.146 | 31.694 | -4.38% | 82.710 | 159.503 | +92.85% | full/full |
| 3 | AB | 33.389 | 31.764 | -4.87% | 85.377 | 146.253 | +71.30% | full/full |
| 4 | BA | 34.029 | 31.849 | -6.41% | 90.377 | 182.004 | +101.38% | full/full |
| 5 | AB | 34.013 | 31.260 | -8.09% | 85.377 | 80.711 | -5.47% | full/full |

### mixed_4_near

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 24.434 | 20.811 | -14.83% | 157.545 | 110.836 | -29.65% | full/full |
| 2 | BA | 24.371 | 20.794 | -14.68% | 135.378 | 93.502 | -30.93% | full/full |
| 3 | AB | 24.364 | 20.826 | -14.52% | 142.378 | 90.919 | -36.14% | full/full |
| 4 | BA | 24.347 | 20.762 | -14.73% | 161.170 | 138.503 | -14.06% | full/full |
| 5 | AB | 24.383 | 20.849 | -14.49% | 140.753 | 92.753 | -34.10% | full/full |

### mixed_4_overload

| Round | Order | A CPU/request us | B CPU/request us | Δ CPU | A RTT p99 us | B RTT p99 us | Δ RTT p99 | Delivery A/B |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | AB | 17.546 | 13.105 | — | 125.545 | 87.836 | — | failed/full |
| 2 | BA | 17.980 | 13.085 | — | 482.596 | 87.711 | — | failed/full |
| 3 | AB | 17.241 | 13.078 | — | 129.504 | 88.210 | — | failed/full |
| 4 | BA | 17.918 | 13.015 | — | 142.212 | 121.962 | — | failed/full |
| 5 | AB | 17.410 | 13.065 | — | 161.755 | 89.377 | — | failed/full |

## Other latency and process-resource observations

Each cell below is the median of five run observations followed by `[min, max]`.
These are per-run p99 observations and resource peaks, not pooled request
percentiles. Overload A's latency values cover only its surviving sample
population; they must be read with the losses below. Process lifetime CPU and
RSS include setup and evidence-record storage. Loadgen CPU additionally includes
input preparation. Peak RSS alone cannot identify the memory cost of a particular
container or explain scheduler effects.

| Scene | Side | Service p99 us | Send-lag p99 us | Loadgen CPU s | Server RSS MiB | Loadgen RSS MiB |
|---|---|---:|---:|---:|---:|---:|
| mixed_4 | A | 24.416 [21.042, 35.042] | 34.755 [30.199, 61.766] | 2.009 [1.963, 2.167] | 36.504 [36.305, 36.527] | 54.137 [54.137, 54.137] |
| mixed_4 | B | 22.125 [21.208, 25.042] | 32.721 [30.535, 46.164] | 1.853 [1.807, 1.947] | 36.504 [36.348, 36.543] | 54.137 [54.137, 54.137] |
| cancel_heavy_4 | A | 22.293 [20.959, 25.876] | 31.522 [30.823, 43.902] | 1.488 [1.398, 1.531] | 36.859 [36.547, 36.867] | 54.137 [54.137, 54.137] |
| cancel_heavy_4 | B | 21.168 [20.959, 23.959] | 31.341 [30.931, 32.276] | 1.464 [1.444, 1.480] | 36.867 [36.645, 36.871] | 54.137 [54.090, 54.137] |
| sweep_4 | A | 27.751 [27.251, 30.376] | 35.961 [33.733, 37.277] | 1.678 [1.653, 1.708] | 38.270 [37.508, 38.270] | 54.137 [54.133, 54.137] |
| sweep_4 | B | 28.334 [27.876, 40.543] | 33.279 [30.913, 68.238] | 1.561 [1.553, 1.587] | 38.270 [38.270, 38.270] | 54.137 [54.133, 54.137] |
| burst_4 | A | 239.330 [124.459, 278.427] | 9767.868 [9498.158, 9989.571] | 2.370 [1.897, 2.824] | 38.270 [38.270, 38.270] | 54.137 [54.133, 54.137] |
| burst_4 | B | 132.294 [122.833, 403.725] | 9746.952 [9610.233, 9970.451] | 1.477 [1.328, 1.654] | 38.270 [38.270, 38.270] | 54.137 [54.090, 54.137] |
| mixed_1 | A | 24.833 [21.418, 26.792] | 32.077 [30.753, 34.955] | 1.607 [1.577, 1.629] | 38.270 [38.270, 38.270] | 53.262 [53.258, 53.262] |
| mixed_1 | B | 38.209 [21.917, 49.626] | 60.545 [31.932, 76.203] | 1.527 [1.475, 1.579] | 38.270 [38.270, 38.270] | 53.262 [53.262, 53.262] |
| mixed_4_near | A | 20.751 [20.209, 21.084] | 35.906 [35.339, 36.908] | 6.861 [6.828, 6.913] | 108.723 [108.238, 108.766] | 227.637 [227.637, 227.645] |
| mixed_4_near | B | 20.042 [19.750, 28.293] | 35.290 [35.069, 44.059] | 5.935 [5.916, 5.953] | 108.723 [108.680, 108.781] | 227.637 [227.633, 227.637] |
| mixed_4_overload | A | 21.417 [18.459, 36.167] | 31.206 [29.351, 32.478] | 4.143 [4.073, 8.156] | 177.738 [177.738, 177.738] | 401.262 [401.262, 401.266] |
| mixed_4_overload | B | 18.376 [18.250, 24.251] | 34.421 [34.352, 37.697] | 7.851 [7.823, 7.877] | 177.738 [177.738, 177.738] | 401.262 [401.262, 401.262] |

One-client mixed has median paired differences of +16.708 us service p99,
+25.590 us send-lag p99 and +0.125 us Gateway p99. These coincide with its RTT
tail regression but do not prove a single causal mechanism. Burst's large RTT
reduction coexists with roughly 9.5–10.0 ms send-lag p99. All latency boundary
and process-lifetime limitations in the [method](../service_benchmark_method.md)
apply. The [completed separate profiling](../m3_report.md#separate-post-experiment-profiling)
covers four-client 45,000/s; it supports the send-amortization mechanism without
establishing the cause of this one-client regression.

## Composed-write observations

The next table gives per-run min–max, including setup. Counts refer to Asio
composed operations; they are not kernel syscall counts. Both variants retain
the same limits. Admission order can change event/BBO frame totals across
clients, so total frame equality is not assumed; Reference validates each actual
trace. A's overload written frames exclude frames conservatively discarded on
close even if a later callback reports transferred bytes.

| Scene | Side | Write operations | Written frames | Send high-water bytes |
|---|---|---:|---:|---:|
| mixed_4 | A | 701,795 | 701,795 | 1,140–3,230 |
| mixed_4 | B | 500,770–501,099 | 701,795 | 1,002–1,416 |
| cancel_heavy_4 | A | 324,180 | 324,180 | 886–4,140 |
| cancel_heavy_4 | B | 219,655–219,791 | 324,180 | 886–2,070 |
| sweep_4 | A | 453,989 | 453,989 | 9,224–9,580 |
| sweep_4 | B | 247,303–248,702 | 453,985–453,989 | 9,224–10,524 |
| burst_4 | A | 677,150–681,115 | 677,150–681,115 | 33,486–34,300 |
| burst_4 | B | 127,970–199,681 | 674,257–680,480 | 25,584–27,680 |
| mixed_1 | A | 401,576 | 401,576 | 1,416–4,444 |
| mixed_1 | B | 199,154–200,842 | 401,576 | 2,832–15,104 |
| mixed_4_near | A | 3,151,705–3,151,776 | 3,151,705–3,151,776 | 4,530–13,996 |
| mixed_4_near | B | 1,817,437–1,844,672 | 3,151,710–3,151,779 | 2,882–4,828 |
| mixed_4_overload | A | 784,833–3,290,791 | 784,830–3,290,790 | 65,450–65,508 |
| mixed_4_overload | B | 2,273,417–2,320,042 | 5,600,821–5,601,410 | 3,346–11,942 |

All formal Matching output-space-wait counters are zero. Every non-overload run
has zero discarded frames, missing business recipients and slow-client closures;
B also records zero for these outcomes at 80,000/s. The byte high-water mark is
queued wire bytes, not total process memory. Buffer descriptors and queued frame
storage remain alive through an active callback after close.

## Every overload loss outcome

Each row has 800,001 planned requests. `Failed` means started but not completed;
`not started` remains distinct. Unfinished is zero in every row. The accounting
identities are `planned = not_started + started` and
`started = completed + failed + unfinished`. All rows drained their admitted
work and passed Reference, including A's five failed client-delivery attempts.

| Round | Side | Started | Completed | Failed | Not started | Slow-client closes | Discarded frames | Missing business recipients |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | A | 201,275 | 200,963 | 312 | 598,726 | 3 | 2,123 | 2 |
| 1 | B | 800,001 | 800,001 | 0 | 0 | 0 | 0 | 0 |
| 2 | A | 201,335 | 201,024 | 311 | 598,666 | 3 | 2,124 | 3 |
| 2 | B | 800,001 | 800,001 | 0 | 0 | 0 | 0 | 0 |
| 3 | A | 400,855 | 400,650 | 205 | 399,146 | 2 | 1,417 | 1 |
| 3 | B | 800,001 | 800,001 | 0 | 0 | 0 | 0 | 0 |
| 4 | A | 201,285 | 200,976 | 309 | 598,716 | 3 | 2,124 | 2 |
| 4 | B | 800,001 | 800,001 | 0 | 0 | 0 | 0 | 0 |
| 5 | A | 600,421 | 600,318 | 103 | 199,580 | 1 | 708 | 0 |
| 5 | B | 800,001 | 800,001 | 0 | 0 | 0 | 0 | 0 |

A records disconnect failures (EOF or connection reset): 2,394,834 requests are
not started and 1,240 started requests fail across five runs. Its 8,496 discarded
frames include 3,675 business frames; there are eight missing business recipients.
The 12 unconfirmed callbacks report 1,336 bytes and 12 complete-frame prefixes,
with zero write-error callbacks. These after-close observations do not reclassify
frames as successfully written or prove receipt. B has zero unconfirmed callbacks.

B fully delivers all five 80,000/s schedules; A fully delivers none. This is a
finite observed delivery outcome, not a paired latency/CPU speedup or a universal
capacity bound. The absolute CPU/request and RTT rows above deliberately retain
the completed-subset values for A, with no delta. A sufficiently large completed
sample cannot conceal the unstarted/failed requests.

## Evidence and remaining checks

The underlying pair report has `evidence_valid=true`, `all_runs_succeeded=false`,
70 measured attempts and 14 warmups. Separate per-variant summaries preserve
30/35 A and 35/35 B measured successes; all drains and Reference checks pass.
Full source and input bindings, every per-round metric and compiled batch limits
are in [m3_service_pairs.json](m3_service_pairs.json). Raw inputs, samples,
server/client records, replay/verification outputs and logs are retained in
`build/m3-measurement/pair-run-1/` and will be included in the durable evidence
archive indexed by the [M3 evidence record](../m3_evidence_index.md).

Separate profiling is complete. Host independent summaries for both 45,000/s
diagnostics exited 0 and reproduced all four source `report.json`/`report.md`
files byte-for-byte; see `build/m3-profiling/host-revalidation/verification.json`.
These instrumented runs remain separate from the formal matrix.

T07 fresh Linux reproduction is also complete, with 104 Release tests across
eight required groups, two actual CLI clients, core smoke and all 14 network
smoke attempts validated. Its three representative 45,000/s pairs fully complete
100,000 requests per measured attempt, but run for about 2.222 seconds each:
`mode=smoke` and `normal_sample_target_met=false` correctly retain the unmet
formal ten-second requirement. Host checks, unchanged-original hashes and
source/derived comparisons are recorded in
`build/m3-clean-repro/host-revalidation/verification.json`. See the
[reproduction report](../m3_report.md#clean-linux-reproduction-and-short-paired-check)
for its fresh-build identities, all three pairs and limitations; the short check
does not replace these 35 formal pairs or reverse their rejection decision.

Final PR/main CI inspection and release publication are separate gates. The release's
[acceptance.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m3-experiments/acceptance.json)
acceptance record binds the actual final source, tested PR/main checkouts and run IDs, and
archive hashes. No future final-check or publication result is claimed here.
