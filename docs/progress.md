# M1 implementation progress

Original specifications remain unchanged. Only observed results count as acceptance.

| Task | State | Evidence / remaining work |
|---|---|---|
| T00 | Verified | Local Debug/Release; actual CI success, deliberate failure and recovery in ci_evidence.md |
| T01 | Implemented / tested | Value/event/snapshot contracts, exact semantics and hand-calculated fixtures; negative oracle probe recorded |
| T02 | Implemented / tested | Independent vector model; shared exact expected events and snapshots |
| T03 | Implemented / tested | map/list/hash book; seven book tests and ASan/UBSan lifetime checks |
| T04 | Implemented / tested | Limit matching both directions, multi-price sweep and output boundaries |
| T05 | Implemented / tested | IOC, cancel, reject precedence, numeric/sequence edges, reused output buffer |
| T06 | Implemented / tested | 40,000 + 1,000,000 differential commands; actual price mutation reduced 2,000 commands to 2; permanent regression and CLI tests |
| T07 | Core verified | Three-job PR CI passed; actual failure traces downloaded/replayed and recovery CI passed (ci_trace_evidence.md); Release benchmark CI pending |
| T08 | Implemented / measuring next | Benchmark, four workload generators and strict report checks implemented; formal five-round measurements pending |
| T09 | In progress | README, ADRs and learning material written; clean-checkout and final report pending |

Initial local tools: Apple clang 21.0.0 (arm64-apple-darwin25.6.0),
CMake 4.4.4, Ninja 1.13.2. A later targeted hardware query verified Apple M5 Pro,
18 physical/logical cores and 48 GiB memory. Remote: https://github.com/Owenqi666/low-latency-matching;
the existing initial commit is preserved. GoogleTest 1.17.0 is pinned by archive SHA256.

The integrated core + trace suite passed 48/48 in Debug and ASan/UBSan.
Release and final feature-branch CI are tracked separately. Development now uses
`feat/m1-baseline` -> PR -> verified merge -> main push verification.
