# M5 acceptance record

Technical implementation, correctness, fixed measurement and fresh Linux
reproduction are verified. Final PR/main identities and permanent archive checks
are recorded in the release's `acceptance.json`; post-upload checks are recorded
in `publication-verification.json`. This source document does not pre-approve
those later gates. The local final check confirms the uploaded receipt itself.

Accepted baseline: `m4-order-storage`,
`9314cf077c3968d484c627aa1d7f7e51dfa28463`. Measured and freshly reproduced source:
`7cea5df6d25c69a99831ed6b00a1babbbf151052`.

| Task | Required evidence | Recorded state |
| --- | --- | --- |
| T00 | Baseline, preserved work and storage | Start receipt and original-file hashes retained; previous matching/network production sources are unchanged. M3 batching and M4 slots remain rejected. |
| T01 | Fixed scope, source/cutoff, workload and timing | [Plan](m5_plan.md), [scope](itch_scope.md) and [ADR](adr/007-independent-itch-reconstruction.md); bounded Nasdaq capture with 1,000 AAPL updates; generation and one-traversal timing fixed before the formal matrix. |
| T02 | Independent decoder/book/CLI and byte contract | Independent C++ module and CLI, 14 C++ tests, hand-maintained golden bytes and expected lifecycle; no MatchingEngine path. |
| T03 | Independent reference, long comparison and four configurations | Direct-byte Python reference; three formal inputs each pass 800,000 target updates and 80 full checkpoints plus final state. Local and fresh Linux Release pass all 124 discovered tests. Candidate CI passes 120/124/120/120 with discovery/JUnit and downloaded-artifact checks. |
| T04 | Genuine historical prefix and representative failure | Continuous 30,262,428-byte day-start AAPL prefix, 1,042,864 payloads and 1,000 target updates; four full checkpoints plus final state agree. Injected overdraw fails at the same frame/reference in both implementations; the current verifier's saved failure command was executed and reproduced that rejection. Original historical receipts remain intact. |
| T05 | Frozen finite matrix and resource observation | Three million-message streams, decode/rebuild modes, six independent warmups and all 30 measured intervals; independent summary passes. One real-prefix resource observation. See [all rounds](benchmarks/m5_itch_rounds.md). |
| T06 | Fresh public source/dependencies/build and complete demonstration | New public clone at 7cea5df in the existing Linux VM, new pinned dependency sources and Release build; all 124 tests, two actual service CLI clients, ITCH golden/real/negative, core/seven-scene network/ITCH smoke pass. Existing real input reused with SHA checked; acquisition was not repeated. |
| T07 | Latest PR, normal merge, exact-main push CI | Required delivery gate, recorded with actual SHA/run/checkout/parent identities in release acceptance.json and validation archive. Candidate green checks alone are insufficient. |
| T08 | Durable archives, tag/release and downloaded-byte verification | Required publication gate, recorded in acceptance.json and publication-verification.json; local final check records the remote receipt's bytes and final Release state. |

## Candidate checks and final source relationship

[Candidate PR CI 39063078708](https://github.com/Owenqi666/low-latency-matching/actions/runs/39063078708)
tested checkout `53dbc147e772f25815d4412577e122829f6ce86e`, with parents M4 baseline
and candidate `7cea5df`. Four downloaded job artifacts passed dynamic test-group
and JUnit checks. Each ITCH CLI suite contains 41 behavioral cases; retained
failure files and verifier replay evidence were checked. The post-download
inspector independently replayed four representative failure inputs and three
positive inputs per configuration with the Python reference, and recomputed core,
seven-scene network and ITCH smoke reports. Four deliberately damaged benchmark
evidence cases were rejected. The inspector's receipt states this bounded replay
scope; it does not claim to execute downloaded platform binaries.

Reporting and post-run inspection helpers are added after the measured commit.
The final `source-relation.json` must compare all 29 measured C++/CMake build
inputs against the final main, bind reference/measurement tools, and list every
post-measurement change. Identical build inputs permit the measurements to remain
valid; new commits still require their own PR/main CI. Historical early long-run
and real-negative receipts keep their original tool identity. The current real
negative check additionally binds the final local Release binary and verifier,
executes the saved command and compares both implementations' failure locations.

## Evidence and limits

The final-source real replay is the fresh Linux T06 run. Real data covers target
A/D/E updates only; synthetic fixtures cover F/C/X/U and the remaining specified
contracts. Neither input hashes nor aggregate checksums replace the independent
state comparisons. The public archive excludes real raw bytes and real state CSV;
the retained local input and documented source/cutoff enable authorized replay.
Only a compressed prefix was consumed, so no complete gzip CRC or full-day source
checksum is claimed.

The VM is shared, without controlled frequency or affinity. These are bounded
batch-throughput/resource observations, not per-message p99, production capacity,
exchange matching reconstruction or a speedup over M1–M4. There is no adoption
threshold or requirement for a positive optimization result.

The [evidence index](m5_evidence_index.md) maps each gate to its durable asset.
The public [reproduction guide](m5_reproduction.md) and checked-in small inspection
tools provide replay entry points. Private plans, VM images, SSH material and
dependency caches are excluded from publication.
