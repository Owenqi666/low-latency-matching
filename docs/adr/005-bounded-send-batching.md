# ADR 005: test bounded batches of already queued output

Status: experiment selected; adoption pending.

M2 writes one encoded frame per Asio composed write. Two new, fully delivered
and Reference-verified mixed diagnostics each show about 701,794 `sendto` calls
for 100,001 measured requests plus setup, matching written-frame counts. Gateway
CPU exceeds Matching CPU in these runs. Kernel/scheduling paths and loadgen still
matter; this does not establish a single end-to-end bottleneck.

Test a maximum of 16 existing queued frames and 4,096 bytes per composed write.
Start immediately when idle and never wait for additional frames. Keep the
socket, protocol, BBO output, two threads, capacities and slow-peer policy. Current
output frames are at most 138 bytes, so the frame bound limits these batches
before the byte bound. Do not change waiting coordination at the same time.

Extract only the concrete send-queue state needed to share real selection,
completion and close behavior with deterministic asynchronous-stream tests.
Preserve a one-frame control with the same extraction and observation fields;
the candidate changes the selected frame constant. Git revisions and independent
builds retain both, without a runtime strategy selector.

Close conservatively counts all unsettled frames, including in-flight ones, as
discarded. Later callbacks cannot count them again as written. Raw callback bytes
and full-frame prefixes are separate diagnostics, not peer-receipt claims. Retain
frame memory until the callback, including when a different callback closes the
connection or adds output during a write.

The [experiment plan](../m3_experiment_plan.md) fixes the comparison and adoption
rule. Potential benefits are fewer writes/callbacks and lower CPU per completed
request. Costs include fixed descriptor storage, callback accounting and possible
tail-latency/fairness changes. Reject the candidate if full correctness and the
predeclared tradeoffs do not hold. A rejected experiment is a valid result; its
source and all measurements remain reproducible.
