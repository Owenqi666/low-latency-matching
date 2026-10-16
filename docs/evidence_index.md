# M1 evidence index

Source implementation: `59a29316a8d91b33bcb5572438eb731a8bc0b96f`.
Reports and acceptance documents may be newer commits; the file hashes in the
result index bind the measured source/build/test/generator files. The final
release records its own merge SHA and independently verified main push CI.

| Question | Evidence |
| --- | --- |
| What are the exact semantics? | [semantics](semantics.md), [trace format](trace_format.md), hand fixture in `data/fixtures/basic.expected.md` |
| Were correctness boundaries tested? | [validation](validation.md), [acceptance mapping](acceptance.md), tests in the source tree |
| Does a broken test really fail CI? | [initial CI failure/recovery](ci_evidence.md) |
| Can event defects be found and minimized? | [local mutation/shrink](t06_evidence.md), permanent two-command regression in `data/regressions/` |
| Were remote failure files actually retrieved? | [CI trace download/replay/recovery](ci_trace_evidence.md) |
| Does the finished implementation run in clean CI? | [59a2931 PR evidence](pr_ci_evidence.md), downloaded logs in the archive |
| Can a clean user reproduce the commands? | [independent checkout reproduction](clean_checkout.md), exact commands, input/output hashes and two actual smoke runs |
| What was measured? | [M1 report](m1_report.md), [method](benchmark_method.md), [all rounds](benchmarks/m1_rounds.md), [JSON](benchmarks/m1_rounds.json) |
| Where are raw results? | [archive identity and download URL](benchmarks/archive.json), [file-level SHA-256 index](benchmarks/m1_result_index.json) |
| How do the core paths work? | [walkthrough](learning.md), [ADR 1](adr/001-book-and-identity.md), [ADR 2](adr/002-capacity-and-results.md) |
| What was ultimately published? | [M1 release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m1-baseline), with exact main SHA and push-CI link |

The evidence archive contains `m1-final/` (all 40 latency and 40 throughput
rounds), `m1-pre-report-fix/` (all earlier rounds), actual generated inputs,
clock probes, verification CSVs, per-round snapshots, selected local correctness
logs/XML, downloaded PR CI artifacts, local failure reduction evidence and
independent clean-checkout logs. The archive's SHA-256 protects the full bundle;
the result index additionally identifies each benchmark file. It contains no
original planning documents.

GitHub Actions artifacts expire according to their retention period; the release
archive preserves the selected implementation evidence independently. Raw
performance results describe this machine and workload, not a hardware-independent
latency guarantee or a network service benchmark.
