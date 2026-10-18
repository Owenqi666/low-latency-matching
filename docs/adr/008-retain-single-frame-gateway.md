# ADR 008: retain one-frame Gateway writes after the new formal comparison

Status: decided; reject batch16 under the frozen rules and retain batch1.
Date: 2026-10-18. Historical local G09 checks and archive recomputation are
recorded in the [report](../gateway_report.md#g09-clean-delivery-verification).
The later default-CI registration issue, revised-source verification and remote
delivery are tracked separately in the [closeout record](../gateway_closeout_2026-10-18.md)
with default Release, extended and ON→OFF local checks verified; current-source
CI and remote delivery remain pending. This ADR records the configuration decision, not a release
or a claim that the current revision has passed CI.

Delivery status below is a pre-merge snapshot; the final head, PR/main checkout
SHAs and CI results are recorded in [PR #7](https://github.com/Owenqi666/low-latency-matching/pull/7).

## Context and fixed comparison

The earlier M3 experiment rejected batch16 because its single-client RTT tail
regressed. This investigation adds bounded tool fixes, independent deep-book
coverage and optional Gateway diagnostics, then rebuilds a fresh minimal A/B
comparison. It does not overwrite [ADR 005](005-bounded-send-batching.md),
[ADR 006](006-fixed-order-storage.md), or their historical results.

A is `7d9d7dc0a6ab386d2d381f401ce644e621e33d33`; B is
`56d5c71e7daec7631272dbc7b10a0f430f3381e0`. Only the SendQueue frame bound
changes from 1 to 16. Both retain 16 descriptors, a 4,096-byte batch bound,
65,536-byte per-connection allowance including in-flight frames, 1,024-slot
command/event queues, the same socket settings and two-thread architecture.
There is no timer to wait for a batch, changed matching rule or admission policy.

The seven-row formal manifest and rules were frozen before launch at
2026-10-18T16:19:55.525998Z, freeze SHA-256
`37646da98a7f6eda9fd287e22937c31869b5fe841d96bc931cd93bf82897f332`.
Tools `f6765b5c0e096428115980c047f56e2a9190146f` and shared A-built loadgen/verifier
were fixed. A-only calibration selected ordinary 10,000/s, near 22,781/s,
burst mean 2,000/s and overload 75,938/s. Its initial stopped attempt,
post-observation classification correction and finite continuation remain
disclosed in the [report](../gateway_report.md#g05-first-probes-and-retained-stop).
They did not rewrite the formal rules after observing B.

Measurements use one Ubuntu 24.04 aarch64 VM, four vCPUs and 4 GiB RAM, with
same-VM loopback server/loadgen on a shared Apple M5 Pro host. Serial unsanitized
Release runs have detailed diagnostics/profilers off. Each row has five
alternating AB/BA pairs and independent A/B warmups: all 70 measurements and
14 warmups were executed and retained. The complete evidence is independently
valid and the original tree was unchanged during recomputation.

## Decision

Retain the measured one-frame control. The full comparison fails the frozen
adoption contract for multiple independently visible reasons:

| Requirement | Formal observation |
|---|---|
| Near CPU/completion median improvement ≥10%, at least four improving pairs | All five improve, but the median reduction is 6.402527% |
| Near RTT p99 median regression ≤10% | +13.717391% |
| Near scheduled-to-complete p99 median regression ≤10% | +10.094805% |
| Both variants fully deliver every ordinary/near measurement | A burst round 2 and A mixed_1 round 4 fail client delivery; B delivers all of them |

The source-bound correctness, bounded-resource and healthy-client-isolation
prerequisites passed. All formal measurements drained admitted work and passed
Reference, and the between-attempt guard found no correctness stop. The runner's
exit 1 preserves valid delivery failures; independent validation exited 0.
This is **reject**, not an inconclusive or invalid experiment.

The two ordinary failures belong to A, not B. Retaining A follows the contract;
it does not claim A is more reliable than B. Near CPU magnitude and both near
latency breaches already prevent adoption independently of those A failures.
Failed-run latency subsets are not used to claim speedup. Four complete
burst/mixed_1 pairs do not satisfy the required five-pair conditions, even though
their descriptive paired medians improve. No failed pair is dropped, no extra
rounds are added and no threshold is relaxed.

## Benefits, costs and limits retained

B fully delivers all 35 formal measurements. In overload it completes all
759,381 planned requests in each of five runs, while A completes 1,145–191,032.
The paired completed/planned difference improves by a median 74.866766 percentage
points. This passes the overload non-regression condition but cannot override
the failed near gates. No paired overload CPU/latency gain is reported because
there are no fully delivered A/B overload pairs.

At near load, lifetime application writes/admitted fall from median 6.992 to
4.892 and written frames/operation rise from 1.000 to 1.429. The primary CPU
quotient includes setup and lifetime overhead divided by measured client
completions. Application writes are not syscall counts, and written frames do
not prove client receipt. Queue and send bounds are unchanged; RSS includes
recording/input storage and is separate from queue occupancy.

Separate G04 profiles show lower observed sendmsg rates and Gateway thread CPU;
they do not explain the later unprofiled near regressions or A failures.
The clean G04 mixed_4 +39.378% RTT p99 outlier remains retained and unexplained.
Formal A mixed_1 also loses delivery at 10k/s, so the earlier successful G04
10k/s runs cannot establish universal reliability. No cross-host improvement,
universal sustainable rate or environmental-fault explanation is claimed.

## G07 and delivery boundary

G07 is **not triggered**. High-water marks and SlowClient closures establish
bounded output pressure, but not a reproducible input-throttle mechanism or
pump starvation. The diagnostic excursion cannot distinguish loadgen,
Gateway, host scheduling and profiler interference. There is no additional
policy change merely to pursue a positive result.

A future scheduling/congestion candidate requires a distinct mechanism-backed
hypothesis, a short ADR before coding, the then-selected production version as
A, and a separately frozen comparison. The current rejection stays intact.

Preserve the common tool, coverage and diagnostic implementation while keeping
the production frame bound at one. Historical local G09 checks bound the
then-selected source to this measured implementation and recorded Linux
smoke/two-client demo/short A/B and independent archive-copy recomputation.
Their two disabled default registrations do not meet the existing strict CI
contract; the closeout must verify the explicit test option and the revised
source's CI without changing the performance gates or rebuilding the archive.
The [full report](../gateway_report.md), [all pairs](../benchmarks/gateway_service_pairs.md),
[diagnostic limits](../gateway_diagnostics.md) and [evidence index](../gateway_evidence_index.md)
retain the historical evidence, outstanding closeout checks and explanatory limits.
