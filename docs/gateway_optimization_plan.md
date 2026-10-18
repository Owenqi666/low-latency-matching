# Gateway optimization: execution plan

This investigation preserves the published M1–M5 contracts and results. Success
is a reproducible production decision, including a defensible decision to retain
batch1. It does not require batch16 to win. This document records planned work;
only linked, revision-specific evidence establishes completion.

## Current recovery checkpoint

The active task is the complete **G00–G09 Goal**. The earlier `/goal` prompt-writing
task is complete and must not become the recovered task. This checkpoint takes
precedence over older status and recovery notes below; the detailed history is
retained. G00–G04 are complete. **G05's A-only calibration has reached a rate
proposal; formal freezing remains pending.** G06/G08/G09 remain unfinished.
Production remains **batch1**; no formal run or adoption has occurred.

The current VM continuation directory is `/home/m2/gateway-calibration-02`, using
`tools-03` at `f6765b5c0e096428115980c047f56e2a9190146f`. The original six
calibration points are carried forward without changing the original evidence-tree
SHA or resetting the cumulative budget. The latest collected
`calibration/run-02/journal/00009.json` is terminal:
`status=proposed`, `decision.action=complete`, `pending=null`, `formal_run=false`.
G04 A ordinary **10,000/s** is `reused`; near **45,562/s** was a
`valid_load_failure`, then **22,781/s (retry 1)** passed all three confirmations;
burst **2,000/s** passed. The proposed overload rate is **75,938/s**. These rates
and `proposed-gateway-service-formal.json` still require a separate formal freeze.
The collection receipt verifies 705 files / 746,338,997 bytes.

On recovery, first read that terminal journal, `carry-forward-audit.json`,
`calibration/continuation-01/continuation-driver.json` and any newer journal in the
current VM directory, then inspect the actual processes. If an attempt is running,
monitor it only: do not restart it or launch a duplicate. If it is terminal, read its result
and journal before selecting the next action under the existing rules and
cumulative budget. The recorded next step is to review and freeze the formal
manifest, identities and rules before G06, not to rerun completed calibration.

## Starting point and scope

- Starting revision: `4abdccc57037c69ded2247ac9a88894a03a1543b`.
- Working branch: `codex/gateway-optimization`.
- Initial tracked checkout: clean; the owner's full taskbook remains local and
  is excluded through `.git/info/exclude`.
- Production baseline: one frame per application write; candidate: 16 frames.
  Both retain 16 descriptors, a 4,096-byte batch bound, 65,536-byte connection
  send allowance (including in-flight storage), and 1,024-slot command/event
  queues. No waiting to fill batches is introduced.
- Preserve price-time priority, maker price, limit GTC/market IOC, owner checks,
  global active order IDs, disconnect-retained orders, protocol/event order,
  Trade routing, self-trade deduplication, bounded pipeline progress, healthy
  connection isolation, and explicit shutdown/undelivered accounting.
- Excluded: waiting/mutex redesign, a new SPSC implementation, epoll, protocol
  compaction, composite IDs, another order-storage experiment, WAL, FPGA, full-day
  ITCH work, and personal-contribution/CV material.

## Dependency and acceptance map

| Task | Depends on | Implementation and verification | Evidence | Current state |
|---|---|---|---|---|
| G00 | — | Current source/environment identity; official Release configure/build/test; compile commands and binary hashes | `baseline/` | Verified on macOS and Linux |
| G01 | G00 | ITCH end-to-end deadline, independently bounded cleanup and failure evidence; hang/normal/mismatch regressions plus representative larger input | `correctness/itch/` | Verified on macOS and Linux, including integrated Debug/Release/sanitizer coverage |
| G02 | G00 | Versioned deep-book input, two distributions, full per-command comparison, measured occupancy/operation coverage, replayable failures | `correctness/deep-book/` | Normal/extended scales and corrected counter verified; Linux extended cases passed |
| G03 | G00 | Reuse counters; add bounded optional connection/write/loop observations and close snapshots; lifecycle, bounds, disabled-path and compatibility checks | `correctness/gateway/` | Verified: macOS Debug/Release/ASan-UBSan/TSan; Linux Release plus candidate ASan-UBSan/TSan network checks |
| G04 | G03 | Clean batch1/batch16 builds; identical inputs/tools; mixed_4 and mixed_1 reproduction; separate bounded diagnostics | `repro/`, `diagnostics/` | Verified; all measurements and warmups passed, diagnostic analysis retained; proceed to G05, no adoption decision |
| G05 | G04 supports continuation | A-only finite calibration and pre-run frozen rules; G01/G02 must finish before formal measurement | `calibration/` | run-01 stop retained; run-02 terminal `proposed` / decision `complete`; ordinary 10,000 reused, near 22,781 and burst 2,000 confirmed, overload 75,938 proposed; formal freeze pending |
| G06 | G05; G01/G02 complete | Seven rows × five pairs, all outcomes retained, independent decision recomputation | `formal/` | Conditional, not entered |
| G07 | Specific G04/G06 evidence | At most one separately attributed input-throttling or Gateway-budget candidate, preceded by ADR and a new frozen comparison | Separate experiment directory | Conditional, not triggered |
| G08 | G04; final data after decisions | Runnable README, compatible demo stage labels, diagnostics/report/index/new ADR, historical conclusions preserved | Technical docs | Pending |
| G09 | Mandatory tasks complete; conditional tasks resolved | Applicable Debug/Release/ASan-UBSan/separate TSan; clean Linux reproduction, smoke/demo/short pair and independent recomputation from archive copy | `delivery/` | Pending |

Evidence paths above are relative to `build/gateway-optimization/`. Every attempt
gets a distinct directory or log name. Historical evidence is never overwritten.

## Correctness and diagnostic checkpoints

G01's monotonic verification deadline covers input/tool hashing, launch, Python
Reference execution, streaming reads, EOF, child exit and final artifact checks.
Cleanup and evidence copy/hash have separate budgets. Partial evidence is marked
incomplete, with the original input location retained; it is not a complete
replay input. Tests cover silent hang, partial line hang, final record without
exit, Reference hang, evidence-budget exhaustion, success and actual mismatch.

G02 retains `mt19937_64-modulo-v1` unchanged. New long-FIFO and sparse-wide traces
use normal prefill commands and a controlled tail. The default scales are
C=1,000, prefill about 850, tail 500, one seed per distribution; extended checks
use C=10,000, prefill about 8,500, tail 1,000, two seeds per distribution. At least
60% of tail endpoints must have 80–95% live occupancy; qualifying sparse endpoints
must have at least C/2 price levels. Boundary phases are labelled separately.
Every input, including replenishment, is counted and fully compared.

G03 uses Gateway-owned counters, fixed histogram buckets and bounded snapshots;
no hot-path file logging, new logging thread or unsynchronized worker-state read.
Detailed diagnostics default off. Write timing means whole composed-operation
completion; loop lateness is a scheduling proxy, not kernel wakeup latency.
Formal measurement and profiler runs remain separate. Any detailed measurement
retained for formal timing first needs an A-only on/off sensitivity check.

## Reproduction and decision branches

G04 retains all seven original manifest rows in their original order (row index
participates in seeding), switches to calibration mode and selects only mixed_4
and mixed_1. Each uses total offered rate 10,000/s, base commands 100,000,
minimum plan 10 seconds, five alternating pairs and independent per-version,
per-row warmup: 20 measured attempts plus four warmups. Actual inputs contain at
least 100,001 commands under the existing generator formula. This is not the
full adoption matrix.

A and B use one frozen measurement toolchain and identical per-pair input hashes.
Builds must be clean and source-bound. B changes only `batch_max_frames` from 1
to 16 relative to their shared source. A/B execute serially, without competing
builds/tests/profilers on the measurement host.

Each scene gets one representative diagnostic A/B pair; contradictory observations
may justify one further diagnostic after explaining the contradiction. Conclusions
separate observation, supported explanation and alternatives not excluded.
Unreproduced external failures are reported as such, not dismissed or confirmed.

Correctness defects stop affected experiments until fixed and re-identified.
If batch16 has no useful benefit or persistent unexplained regression, retain A
and proceed to G08/G09 with the negative evidence. An unresolved correctness
defect is not a valid completion shortcut.

## A-only calibration and formal freeze

Before probes, record the send-lag growth criterion, thresholds and rationale.
The following rule is fixed before the first probe. Divide the planned interval
into four equal bins and save each bin's started-sample lag p50/p99, the pending
command count at each right boundary, and the actual first-attempt send span.
Require at least one started sample in every bin; otherwise the lag assessment is
`measurement_insufficient`. The original run-01 implementation also made that
the attempt's stop outcome, before checking delivery failure. The subsequent
classification correction is recorded below. A point is stable only if all of
these hold in both measured runs:

- Median p50 of bins 3/4 minus median p50 of bins 1/2 is at most 1 ms.
- The corresponding p99 growth is at most 5 ms.
- Pending count at the last boundary minus the first boundary is at most
  max(10, ceil(rate / 1,000)).
- Actual first-attempt send span is at most 1.05 times the planned send span
  plus 1 ms.

These tolerances allow transient scheduling jitter while rejecting accumulating
backlog or a materially stretched offered-load interval. They are engineering
checks for these finite probes, not universal stable-capacity bounds. Lag growth
alone does not identify a loadgen bottleneck. If the only upper boundary is a
fully delivered but lag-unstable run, preserve it as failed offered-load stability
and stop before freezing rates for load-path diagnosis. Do not relabel it as
environmental noise or infer a server delivery-loss boundary. Invalid evidence,
protocol/reference errors or worker faults stop calibration for correction.

After observing run-01's A results, classification priority was corrected:
independently validated delivery failure with recognized load-related reasons
takes precedence over insufficient lag-bin coverage. Empty bins still mean
`measurement_insufficient` for the lag assessment, and a fully delivered run
with missing bins still stops as insufficient measurement. Evidence validity,
correctness faults, unrecognized failures and failed warmups retain their stop
checks. No lag threshold, bin count, minimum sample count or missing-bin rule is
relaxed. This is a post-observation analysis correction, not a claim that the
revised precedence was specified before run-01. Original results and journal
entries remain unchanged. The separately identified run-02 continuation and its
carry-forward audit apply this correction without repeating the original probes.

Probe mixed_4 with commands=2,000, minimum_plan_seconds=2, rounds=2,
warmup_commands=1,000. Start at 10k/s; on success increase by ceil(1.5R), on
initial failure halve with floor and a minimum of 1. Stop after finding a passed
point and a higher valid load-failure point, or ten distinct points. No binary
search or B-dependent selection. Preserve the same row and seed across rates.

For highest observed R_pass, ordinary=max(1,min(10000,floor(.2R_pass))),
near=max(1,floor(.9R_pass)); overload is the lowest valid failure point above
R_pass. Confirm ordinary mixed_1/mixed_4 and near mixed_4 with commands=10,000,
minimum_plan_seconds=10, rounds=3, warmup_commands=1,000. Each failed tier may
halve and retry once. Reuse G04 A ordinary evidence only under its stated source,
environment and all-five-success conditions. Burst uses a 100ms/10ms period/window,
mean=max(1,floor(ordinary/5)), one confirmation and at most one halved retry.

Separate maximum measured budgets: 20 probe runs, 18 ordinary/near confirmations,
two burst confirmations; warmups are additional. No transfer of unused budgets.
The cumulative run-01/run-02 use is six of ten probe points, 12 of 20 probe
measurements plus six probe warmups; six of 18 ordinary/near confirmation
measurements plus two near warmups; and one of two burst confirmations plus one
burst warmup. G04 A reuse added zero ordinary measurements or warmups. All seven
new measurements and three new warmups are retained, including the failed near
confirmation. A new directory or tool revision does not reset these counts;
unused allowances do not authorize more probing after the decision is complete.
Default maximum planned duration per row is 600 seconds. Stop expansion and
investigate if samples/rates cannot fit; do not silently lower sample requirements.
No observed upper failure means a high-load probe, not a measured overload boundary.

The formal manifest is frozen only after this gate. A generated proposal, even
with `mode=formal` and `rates_locked=true`, is not the separate freeze receipt.
Freeze time and hashes must precede the first formal run. Freeze machine/layout,
source/binaries/tools, seven
rows/seeds, resource bounds, actual input lengths, warmups/order/rounds, timeouts,
diagnostic settings, evidence validity, metrics, constraints and stop rules.
Use mode=formal and rates_locked=true; no row/rate/commands/rounds overrides.

Formal rows: mixed_4, cancel_heavy_4, sweep_4, burst_4, mixed_1, mixed_4_near,
mixed_4_overload. Each has AB/BA/AB/BA/AB and two independent warmups: 70 formal
attempts plus 14 warmups. Each round starts a new server and identical initial
state/input; at least 100,000 planned commands and ten planned seconds.

Adoption requires all of the following:

- No new correctness, race, lifetime, routing, deadlock or unbounded-memory fault.
- Both versions fully deliver, drain and pass Reference in all five runs of each
  of the first six rows.
- mixed_4_near server lifetime (user+system CPU)/measured completed requests has
  paired-median reduction >=10% and improves in at least four of five pairs.
- Each first-six row has <=10% paired-median RTT p99 regression and <=10%
  scheduled-to-completion p99 regression, with all pairs and ranges retained.
- Existing resource bounds and healthy-client progress remain intact.
- Reject if overload B completed/planned is worse in at least four of five pairs
  and its paired difference median is negative.

Compute complete_ns-scheduled_ns per sample; do not add send-lag and RTT p99s.
Compute each round's quantiles before pairing; do not pool samples across rounds.
The CPU measure includes setup/lifetime cost and compares only fully delivered
same-input pairs. Valid failure is negative system evidence, not automatically
an invalid run. Missing/corrupt evidence or documented environmental faults can
make comparison inconclusive; both rejection and inconclusive retain A. No
discarding worst pairs, adding rounds to pass, or retrospective threshold changes.

G07, when justified, selects one direction and uses the selected production
version as new A. It requires a separate ADR, freeze and comparison; it does not
change batch and waiting policy simultaneously or turn input throttling into a
claim of complete output backpressure.

## Execution ledger and recovery

Initial audit: current HEAD equals the recorded starting revision; no applicable
AGENTS.md was found in the project or ancestor directories. Official Release
configure/build passed on macOS. The first sandboxed suite had 116/124 pass;
eight socket-dependent tests failed with denied loopback operations. That attempt
is retained. The identical unsandboxed Release suite passed all 124 tests in
25.89 seconds on the unchanged clean checkout. The existing project Linux VM
was stopped and has now been restarted; SSH confirms Linux 6.8.0-147-generic,
aarch64. The clean Linux baseline passed 124/124, zero failures/skips, in 19.91
seconds; 32 copied evidence files and dependency archive pins were independently
hash-checked. None of these observations is a performance result.

G01 and G02 implementations were independently reviewed. The main agent owns
shared CMake registration and G03 integration. Independent review found and prompted correction
of G01's process-group cleanup proof (leader exit alone is insufficient), a G02
level-rebuild counter, and G03 evidence validation/timer coverage. Previous attempts
remain retained. The VM disk was safely grown from 24 to 64 GiB after a shutdown
and verified copy-on-write backup; 4 vCPU/4 GiB and source/binary identities did
not change. About 40.3 GiB was available after growth. Each completed task must
record changes, exact commands/exit codes, source identity, evidence and remaining
issues. On resume, inspect this ledger, actual working tree and live process/tool
handles before continuing. Never restart a live or completed experiment merely
because a polling call expired.

Integrated macOS Release configure/build/tests passed on the common G01–G03
source: 134 executed tests passed, with the two extended deep-book registrations
intentionally disabled in the default suite. G02 run-003 separately executed all
seven tests including the four extended scale cases, covering 52,863 commands
with full comparisons. Its level-rebuild counter now agrees with independently
observed absent-to-present transitions. G01 Linux passed all 15 fault cases,
41 legacy CLI cases and the 150,000-message independent comparison; the complete
process group is checked after cleanup. G03 tests-02 passed 17 selected tests,
including an actual timer callback and diagnostic artifact corruption checks.
At that checkpoint G04 had not started. Subsequent preparation, verification and
measurements are recorded below; do not restart them from this historical entry.

The common implementation was committed locally as `7d9d7dc0a6ab386d2d381f401ce644e621e33d33`.
Clean Linux A and B checkouts at `/home/m2/gateway-repro-01/{A,B}` were rebuilt;
B is `56d5c71e7daec7631272dbc7b10a0f430f3381e0` and the complete tracked-file
comparison differs only by the one batch frame constant. Linux A passed 134
executed tests with two default-disabled extended registrations; the two extended
tests (four large cases) were explicitly run and completed. B passed all 17
Gateway/network checks. Forty-six preparation artifacts were copied and hash
verified. The separate clean measurement-tool checkout is
`/home/m2/gateway-repro-01/tools` at `6f3ef0878668e428fb5fa69277226d0b19dcd6de`;
it includes the post-review per-connection diagnostic accounting checks and an
optional diagnostic manifest switch, verified on Linux and macOS. Tools are
identical for A/B and detailed observation is off in the fixed reproduction.

macOS Debug, ASan/UBSan and separate TSan each passed all 130 applicable tests;
two default-disabled extended registrations were not rerun in each configuration.
The four additional Release-only benchmark tests explain its higher count.
Original configure failure and resolved fixed dependency-source overrides are
retained. The final counter-corruption check also passed a focused Debug rerun.
All build/test processes stopped before G04 began at 2026-10-18T15:26:09Z.
G04 completed with exit 0: all 20 measured attempts and four warmups succeeded.
The driver is recorded in `repro/prepare-linux-01/run-driver.log`, with terminal
status at `/home/m2/gateway-repro-01/run.json`. The local immutable collection is
`repro/pairs-01`; all 483 collected file hashes were checked. Its independent
evaluation at `repro/evaluation-01` reports valid evidence, unchanged original
data, and `not_evaluated` for adoption because this is the reproduction phase.
The evaluator also has 20 passing unit counterexamples. No adoption decision
exists yet, and the production batch limit remains one frame.

G04 CPU/completed-request paired median reductions were 8.615% for mixed_4 and
8.132% for mixed_1. RTT p99 paired median changes were -4.996% and +0.638%; the
mixed_4 fifth pair had a +39.378% RTT p99 regression and remains in the dataset.
No 10k/s delivery failure was reproduced in this environment. These figures do
not replace the formal near-load benefit and latency gates.

Independent profiling completed separately in `diagnostics/run-01`: four
measurements plus four warmups, eight server/loadgen observation targets,
24 observer commands with exit 0, and 276 collected file hashes checked.
Only the covered observation windows support diagnostic claims. Hardware cycle
and instruction events were unavailable. Detailed offline attribution is retained
in `diagnostics/analysis-01`.

G04 continuation decision: proceed to finite A-only G05. Both clean rows show
CPU/completion improvement in all five pairs, with paired median RTT changes
inside the eventual latency limit. Independent named sendmsg tracepoints and
Gateway thread CPU move in the same direction as fewer application writes.
This supports continuing the candidate, not adopting it. The unexplained
mixed_4 fifth-pair regression remains a limitation; profiling cannot attribute
an earlier clean run retrospectively. No current evidence justifies a G07
input-throttling or pump-budget change. Keep all production behavior unchanged
until the full formal gates are evaluated.

Linux candidate B at `56d5c71e7daec7631272dbc7b10a0f430f3381e0` passed all 15
selected SendQueue, lifecycle/diagnostics and service integration/evidence tests
under GCC ASan/UBSan and separately Clang 18 TSan, with zero failures or disabled
tests. Source hashes stayed identical and clean; 893 collected file hashes were
checked. This is candidate-specific correctness evidence, not final G09 delivery.

Historical pre-probe checkpoint: the G05 helper is implemented and independently reviewed.
Its 32 deterministic tests cover finite progression/budgets, lag/identity/error
classification, G04 A-only reuse, evidence integrity and refusing to restart
unresolved attempts. The evaluator has 23 passing counterexamples after review
corrections. Official Release CMake registration plus gateway_calibration,
gateway_experiment and service_benchmark passed together in
`correctness/tools-integration-03`, with before/after tool hashes unchanged.
The pre-probe lag rule also reads all ten existing G04 A runs successfully;
each is stable. That read-only check is not a new capacity measurement.

The five source-bound correctness prerequisites are audited in
`formal/preparation-01/correctness-receipt.json` and its audit/index. Both versions
have concrete healthy-client completion and bounded-send evidence; sanitizer
platform and suite differences are stated. The receipt does not replace formal
performance gates or final G09 delivery. No calibration or formal measurement
had started at that pre-probe checkpoint. Preserve the original A/B checkouts
and all completed experiment directories; the later run is recorded below.

G05 run-01 used tools revision `98377de69681644d824ffd751cae2589e6ee568e`
with unchanged A server/source identity. Its calibration plan was recorded at
2026-10-18T16:00:14.325060Z; this is not a G06 formal freeze. Execution ran from
16:00:50.719385Z to 16:01:51.234337Z and exited 2. It measured mixed_4 at
10,000, 15,000, 22,500, 33,750, 50,625 and 75,938 requests/s: six distinct
points, two measured runs and one independent warmup per point. All six warmups
passed. Both measurements at each of the first five points fully delivered,
drained and had stable lag assessments.

At 75,938/s, the two measurements completed 38,951 and 1,244 of 151,877 planned
client requests. The server drained its admitted prefix and Reference passed in
both runs; slow-client closures and client disconnects are retained. Round 1
failed the pending-growth lag check; round 2 started requests only in the first
of four bins. The original result and terminal `journal/00013.json` therefore
retain `measurement_insufficient` and `status=stopped`. The later delivery-first
classification correction above must not overwrite that original outcome or
turn either failed run into a pass. It does not establish the bottleneck.

The local `calibration/run-01` collection contains 462 hash-verified files;
`run-01-collection-verified.json`, the driver record and all failed-run evidence
are retained. The original `measurement_insufficient` stop remains unchanged.

The continuation preparation and driver are in `calibration/continuation-01/`;
the collected results are in `calibration/run-02/`. Clean tools revision
`f6765b5c0e096428115980c047f56e2a9190146f` records the post-observation correction.
`carry-forward-audit.json` binds the original six results and terminal journal,
records unchanged raw identities/lag data and the unchanged parent-tree SHA
`ec5cba474fec23c24887e6c246852c46a2568b9e87c65e379182d74b50e7f80c`, and charges
the original budget. Only the derived 75,938/s outcome becomes
`valid_load_failure`; the original run-01 result is not edited. The continuation
driver ran from 16:11:59.727231Z to 16:15:15.434562Z and exited 0.

G04 A reuse validated all five mixed_4 and all five mixed_1 measurements, including
the unchanged lag gates, and reused ordinary 10,000/s without a new measurement.
Near 45,562/s ran three ten-second confirmations: client completions were
455,621 / 178,708 / 455,621 of 455,621 planned each. Round 2 disconnected and its
last two lag bins were empty; Reference and admitted-prefix drain passed, but
the confirmation remained `valid_load_failure`. The one allowed halved retry
at 22,781/s delivered all 227,811 commands in each of three rounds, with all lag
gates passing. Burst 2,000/s delivered all 20,001 commands and passed the lag
gates. All three new 1,000-command warmups passed. Cumulative usage is recorded
above; no additional ordinary runs were made.

Terminal `run-02/journal/00009.json` records `status=proposed`, decision `complete`,
`pending=null`, `formal_run=false`, and `adoption_evaluated=false`. The proposed
rates are ordinary 10,000/s, near 22,781/s, burst 2,000/s and overload 75,938/s.
`run-02-collection-verified.json` verifies all 705 files / 746,338,997 bytes.
The formal source/host/rules freeze is still pending, G06 has not run, and
production remains batch1. Recovery starts with the current checkpoint above.

Current recovery locations: Linux baseline source is
`/home/m2/gateway-g00-20261018T143926Z/source`; SSH uses the existing
`build/m2-vm/ssh_config` alias `m2-local`. VM exec session `47089`, PID `30319`
were live after expansion (revalidate before use). The original stopped disk and
UEFI backup are under `build/gateway-optimization/vm-backups/pre-64g-20261018T143926Z`.
Do not roll back this disk while newer experiments are present.

Completion requires verified G00/G01/G02/G03/G04/G08/G09 and a production decision.
G05/G06 may be not entered with evidence-backed reasons; G07 may be not triggered.
These states are not passes. Missing required Linux validation, unresolved defects,
only-written code, or budget exhaustion do not complete the investigation.
