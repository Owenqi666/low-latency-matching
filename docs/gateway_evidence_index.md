# Gateway evidence index

All paths below currently refer to local evidence under
`build/gateway-optimization/`; final archival identities will be added only after
the archive has been created and independently verified. Historical M1–M5 assets
and conclusions remain unchanged.

| Evidence | Location | Meaning |
|---|---|---|
| Source identity and local taskbook hash | `baseline/source.json` | Starting revision and clean tracked source before changes |
| macOS toolchain and dependency pins | `baseline/environment-macos.json` | Actual local tools; not Linux validation |
| Official configure/build and first test attempt | `baseline/results-macos.json`, `baseline/*-macos.log` | Configure/build success; sandbox loopback failures retained |
| Identical suite with loopback permitted | `baseline/test-macos-loopback-enabled.json`, `.log` | Exit 0; 124/124 passed in 25.89 seconds on unchanged clean source |
| macOS binary hashes and compile commands | `baseline/binaries-macos.json`, `baseline/compile_commands-macos.json`, `baseline/CMakeCache-macos.txt` | Binary/build provenance when generated |
| Linux baseline | `baseline/linux-20261018T143926Z/guest/`, `host-verification.json` | Clean fixed source, Release 124/124 with no failure/skip; 32 copied file hashes and dependency archive pins verified |
| VM disk preparation | `baseline/linux-20261018T143926Z/disk-growth-*` | 24 to 64 GiB, original disk/UEFI backed up and hashed, guest filesystem grown, baseline source/binaries rechecked |
| ITCH local failure/normal regressions | `correctness/itch/run-1x5s9jqz/` | 15 cases including leader-exit and whole-group forced kill; macOS process-group cleanup verified |
| ITCH legacy CLI and larger input | `correctness/itch/legacy-cli/run-h772sp9p/`, `correctness/itch/long-150k/` | 41 legacy cases; 150,000 messages/120,000 updates/12 checkpoints passed; corresponding Linux evidence below |
| Deep-book local scales and counter correction | `correctness/deep-book/run-003/` | Seven tests passed including four extended cases; six scale traces, 52,863 fully compared commands; independent rebuild-count regression and replay; run-002 preserved |
| Gateway local regressions | `correctness/gateway/tests-02.*` | 17 selected tests passed, including actual timer and corruption checks; tests-01 preserved |
| ITCH Linux verification | `correctness/itch/linux-20261018T145329Z/results/linux-acceptance.json`, `collection-manifest.json` | 15 fault cases, 41 legacy CLI cases and 150k-message comparison passed; 424 collected files hash checked |
| Integrated common source on macOS | `correctness/integration-macos-01/` | Official Release configure/build passed; 134 executed tests passed, two extended registrations disabled by default; source/binary hashes and JUnit recorded |

See [execution plan](gateway_optimization_plan.md) for the dependency map and
completion contract. New correctness, reproduction, profiling, calibration,
formal and delivery records will be indexed as they are actually produced.
