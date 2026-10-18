# Gateway evidence index

All paths below currently refer to local evidence under
`build/gateway-optimization/`; final archival identities will be added only after
the archive has been created and independently verified. Historical M1–M5 assets
and conclusions remain unchanged.

Current recovery entry: [the execution plan's checkpoint](gateway_optimization_plan.md#current-recovery-checkpoint),
`calibration/run-02/journal/00009.json` and
`calibration/continuation-01/continuation-driver.json`. Calibration is terminal
`proposed` / decision `complete`; the separate formal freeze and G06 remain
pending. Production remains batch1.

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
| Clean Linux A/B preparation | `repro/prepare-linux-01/guest/`, `host-verification.json` | A Release 134 executed passes; explicit extended deep-book runs; B 17 Gateway/network passes; 46 artifact hashes verified and only constant differs |
| macOS Debug and sanitizers | `correctness/macos-matrix-01/summary.json` | Debug, ASan/UBSan, separate TSan each 130 passes + two disabled extended registrations; command/source/binary identities retained |
| Diagnostic-counter and runner correction | `correctness/gateway/tests-03.*`, `tools-01.*`, `repro/prepare-linux-01/tools-validation.log` | Corrupt per-connection counters rejected; optional diagnostics checked and formal runner exclusion verified |
| G04 pre-run conditions | `repro/prepare-linux-01/execution-plan.json`, `host-environment.json` | Fixed 20 measured attempts + four warmups, source/tool IDs, actual host and limits |
| Completed G04 reproduction | `repro/pairs-01/`, `repro/pairs-01-collection-verified.json` | All 20 measurements and four warmups passed; 483 collected file hashes verified; includes the mixed_4 RTT regression pair |
| Independent G04 recomputation | `repro/evaluation-01/gateway-evaluation.json`, `.md` | Valid reproduction evidence; original data unchanged; adoption remains not_evaluated |
| Evaluator review corrections and recomputation | `correctness/gateway-evaluator-fixes-01/`, `repro/evaluation-02/` | 23 counterexample tests passed; rejects forged client/scenario settings and malformed timestamps; preserves valid numeric rejection if an additional correctness receipt is invalid; real G04 metrics unchanged |
| Independent diagnostic collection | `diagnostics/run-01/`, `diagnostics/run-01-collection-verified.json` | Four measurements plus four warmups; eight targets observed, 24 observer commands exited 0; 276 file hashes verified |
| Offline diagnostic attribution | `diagnostics/analysis-01/` | Reproducible script/JSON/report and four timelines; 74 consumed evidence files hash checked; syscall/CPU/stack evidence and temporal/coverage limits retained |
| Linux batch16 candidate sanitizers | `correctness/linux-b-sanitizers-01/summary.json` | ASan/UBSan and separate TSan each passed 15 selected tests, no disabled or failed tests; clean unchanged B source, 893 transferred files hash verified |
| Current tools and staged demo integration | `correctness/tools-integration-02/` | Configure, service_benchmark and gateway_experiment passed; two real CLI clients passed seven-command Gateway G08 demo with independent verification; later evaluator fixes are checked separately above |
| Reviewed calibration and evaluator integration | `correctness/tools-integration-03/` | Official configure and three focused CTest entries passed; 32 calibration and 23 evaluator cases; tool hashes unchanged during checks |
| Pre-probe host and lag checks | `calibration/host-preflight-01.json`, `calibration/g04-lag-assessment-01.json` | Actual host layout/AC power rechecked; frozen lag criterion passes existing G04 A evidence; no new measurement |
| G05 first A-only probe sequence | `calibration/run-01/`, `calibration/run-01-driver.json`, `calibration/run-01-driver.log` | Six rates from 10,000 to 75,938/s; 12 measured runs plus six warmups; first five points passed; original terminal outcome is `measurement_insufficient`, driver exit 2 |
| G05 immutable collection verification | `calibration/run-01/collection-sha256.json`, `calibration/run-01-collection-verified.json` | All 462 collected file hashes match; includes both 75,938/s delivery failures, their raw lag bins, original results and terminal `journal/00013.json` |
| G05 classification correction and carry-forward | `calibration/continuation-01/tools-preparation.json`, `calibration/run-02/carry-forward-audit.json`, `plan.json` | Clean tools `f6765b5`; post-observation delivery-failure precedence correction; original tree SHA, six raw probe identities and lag data unchanged; original stop retained; cumulative budgets preserved |
| G05 ordinary reuse | `calibration/run-02/g04-reuse.json` | G04 A identity and all five rounds of each ordinary row checked; ten stable lag assessments; 10,000/s reused with zero new ordinary measurements |
| G05 near and burst confirmations | `calibration/run-02/attempts/007-near-45562/`, `008-near-22781/`, `009-burst-2000/` | 45,562/s retained as valid delivery failure (round 2: 178,708/455,621 complete, two empty lag bins); allowed halved retry 22,781/s passed all three rounds; burst 2,000/s passed; seven new measurements and three warmups retained |
| G05 terminal proposal and collection | `calibration/continuation-01/continuation-driver.json`, `calibration/run-02/journal/00009.json`, `proposed-gateway-service-formal.json`, `calibration/run-02-collection-verified.json` | Driver exit 0; terminal `proposed` / decision `complete`, no pending attempt; proposed ordinary/near/burst/overload rates 10,000/22,781/2,000/75,938; 705 hashes / 746,338,997 bytes verified; no formal freeze, G06 run or adoption |
| Source-bound correctness prerequisites | `formal/preparation-01/correctness-receipt.json`, `correctness-audit.md`, `artifact-index.json` | Five prerequisite categories audited against A/B sources and concrete test artifacts; platform/scope limitations retained; not a formal adoption or G09 receipt |

See [execution plan](gateway_optimization_plan.md) for the dependency map and
completion contract. New correctness, reproduction, profiling, calibration,
formal and delivery records will be indexed as they are actually produced.
