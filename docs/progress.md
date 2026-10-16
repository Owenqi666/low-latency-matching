# M1 implementation progress

Original specifications remain unchanged. Only observed results count as acceptance.

| Task | State | Evidence / remaining work |
|---|---|---|
| T00 | In progress | Debug and Release configure/build and 1/1 test passed locally; remote CI/failure probe pending |
| T01 | Pending | Full value/event/snapshot contracts and manual expected cases |
| T02 | Pending | Independent reference model |
| T03 | Pending | Baseline order book |
| T04 | Pending | Limit matching |
| T05 | Pending | Market, cancel and boundaries |
| T06 | Pending | Differential replay and shrinking |
| T07 | Pending | Sanitizers, actual CI and failure evidence |
| T08 | Pending | Reproducible core benchmark |
| T09 | Pending | Clean-checkout delivery and learning material |

Initial local tools: Apple clang 21.0.0 (arm64-apple-darwin25.6.0),
CMake 4.4.4, Ninja 1.13.2. CPU model/memory sysctl was denied by the sandbox;
no hardware details are inferred. Remote: https://github.com/Owenqi666/low-latency-matching;
the existing initial commit is preserved. GoogleTest 1.17.0 is pinned by archive SHA256.
