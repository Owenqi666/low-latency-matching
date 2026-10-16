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
| T06 | In progress | Strict text IO integrated; differential/replay/shrinking under development |
| T07 | Pending | Sanitizers, actual CI and failure evidence |
| T08 | Pending | Reproducible core benchmark |
| T09 | Pending | Clean-checkout delivery and learning material |

Initial local tools: Apple clang 21.0.0 (arm64-apple-darwin25.6.0),
CMake 4.4.4, Ninja 1.13.2. CPU model/memory sysctl was denied by the sandbox;
no hardware details are inferred. Remote: https://github.com/Owenqi666/low-latency-matching;
the existing initial commit is preserved. GoogleTest 1.17.0 is pinned by archive SHA256.

The integrated core + trace suite passed 48/48 in Debug and ASan/UBSan.
Release and final feature-branch CI are tracked separately. Development now uses
`feat/m1-baseline` -> PR -> verified merge -> main push verification.
