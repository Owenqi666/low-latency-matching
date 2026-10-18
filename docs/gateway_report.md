# Gateway optimization report

Status: investigation in progress. Production remains **batch1**. G00–G04 have
verified evidence; G05 calibration tooling is being completed. The formal
adoption matrix, final ADR and G09 delivery verification are not yet complete.
This report must not be read as a release or adoption receipt.

## Scope and source identity

The first comparison changes only `batch_max_frames` from 1 to 16. Both variants
retain 16 descriptors, a 4,096-byte batch limit, 65,536-byte per-connection send
allowance including in-flight data, and 1,024-slot command/event queues. There is
no wait-to-fill timer, new admission policy or changed matching semantics.

| Role | Source |
|---|---|
| Original baseline | `4abdccc57037c69ded2247ac9a88894a03a1543b` |
| Common implementation / experiment A | `7d9d7dc0a6ab386d2d381f401ce644e621e33d33` |
| Experiment B, frame constant only | `56d5c71e7daec7631272dbc7b10a0f430f3381e0` |
| Frozen G04 measurement tools | `6f3ef0878668e428fb5fa69277226d0b19dcd6de` |

A/B binaries were rebuilt from clean Linux checkouts and their build inputs
were compared. Both use the same A-built loadgen and independent verifier.
Later analysis-tool changes are identified separately and do not alter the
frozen measurement tools or raw data.

## Environment and measurement boundary

Measurements ran on Ubuntu 24.04 aarch64, kernel 6.8.0-147-generic, in the existing
QEMU/HVF VM with four vCPUs and 4 GiB RAM. Server and loadgen share the VM and use
TCP loopback. The host is an Apple M5 Pro, 18 CPU cores and 48 GiB RAM, running
macOS 26.6.2 on AC power. Cores are not exclusive and frequency is not controlled.
Hardware-cycle/instruction perf events were unavailable; diagnostic software
sampling and the named syscall tracepoints were available.

Clean A/B runs were serial, unsanitized Release, with detailed Gateway diagnostics
off and no competing project builds, tests or profiler runs. Profiling is a
separate dataset. Results characterize this layout and workload only.

## G04 fixed reproduction

Each of mixed_4 and mixed_1 used a total offered rate of 10,000/s, five alternating
AB/BA pairs and separate A/B warmups. All seven manifest rows and their original
indices were retained; selection used the runner's row arguments. Every measured
input contained 100,001 commands with a ten-second planned interval. All 20
measurements and four warmups fully delivered, drained and passed Reference.
The external report's 10k/s delivery failure was not reproduced here.

| Row | CPU/completion reduction, paired median [min, max] | RTT p99 change, paired median [min, max] | Scheduled-to-completion p99 change, paired median [min, max] |
|---|---|---|---|
| mixed_4 | 8.615% [7.566%, 11.935%] | -4.996% [-14.369%, 39.378%] | 0.054% [-6.824%, 35.435%] |
| mixed_1 | 8.132% [5.250%, 9.645%] | 0.638% [-13.916%, 2.947%] | -1.846% [-4.736%, 5.032%] |

Positive CPU reduction means lower B cost; positive latency change means B is
slower. CPU is server lifetime user+system CPU divided by measured client
completions, including setup/lifetime overhead in the numerator. Quantiles are
computed separately in each run before pairing; scheduled-to-completion is
computed per sample as `complete_ns - scheduled_ns`, not a sum of p99s.

The fifth mixed_4 pair regressed in RTT p99 from 84.544 to 117.836 microseconds
(+39.378%). It is retained and unexplained. Profiling a different run cannot
retrospectively establish its cause. The complete per-pair values and raw data
remain in `build/gateway-optimization/repro/pairs-01/`; independent recomputation
is in `repro/evaluation-02/` under that evidence root, including raw per-request
scheduled-to-completion quantiles and before/after input-tree hashes.

## Diagnostic interpretation and next decision

The [diagnostic report](gateway_diagnostics.md) separates observations, supported
explanations and remaining alternatives. In the observed windows, named sendmsg
rates fell about 28.8% for mixed_4 and 50.0% for mixed_1. Gateway thread CPU fell
while Matching thread CPU changed little. Retained stacks support both network
delivery and synchronization costs; they do not establish matching-core
saturation. Diagnostic tail co-occurrence does not prove causation.

G04 supports entering the bounded A-only calibration: CPU/completion improved in
all five pairs of both rows, application writes and observed syscalls decreased,
and neither clean row had a persistent median latency regression. This is not an
adoption decision. G05 must validate offered-load stability and freeze all seven
formal rows before G06 can apply the predeclared benefit, latency, delivery,
resource and isolation gates. No evidence currently triggers a G07 policy change.

## Acceptance and remaining work

The [execution plan](gateway_optimization_plan.md) contains the task-by-task
status and recovery point; the [evidence index](gateway_evidence_index.md) locates
raw commands, source/binary identities and validation logs. G01 includes bounded
whole-process ITCH verification; G02 includes full per-command deep-book coverage;
G03 includes optional bounded diagnostics and lifecycle/accounting checks.

Still required: complete G05 and its entry/exit decision; if its conditions hold,
run the frozen G06 matrix and decide production configuration; record G07 as
triggered or not triggered; finalize this report and a new ADR; finish the clean
Linux build/smoke/demo/short A/B and archive-copy recomputation required by G09.
The current passing sanitizer results do not by themselves complete G09.

Historical [M3 rejection](m3_report.md) and [M4 rejection](m4_report.md) are
unchanged. No personal-contribution or CV claim follows from this investigation.
