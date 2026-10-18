# Gateway evidence index

All paths below currently refer to local evidence under
`build/gateway-optimization/`, except the single archive directory explicitly
marked repository-relative below. Archive identities are verified. Historical M1–M5 assets
and conclusions remain unchanged.

Current recovery entry: [the execution plan's checkpoint](gateway_optimization_plan.md#current-recovery-checkpoint),
`formal/freeze-01/freeze.json` and `formal/run-01-driver.json`. G05 is complete;
G06 retained all 84 attempts and its driver ended at 16:47:47.105786Z. Runner
exit 1 retains delivery failures; summarizer exit 0 and all 84 guard checks
completed without a stop. Independent evaluation completed at 16:54:55.338036Z,
exit 0: valid evidence, reject batch16, retain batch1. G07 is not triggered.
G08 is committed at `4cb1cc5`; G09 fresh Linux verification, smoke/demo and short
replay passed and were collected. The single raw archive is readable and its
extracted-copy formal recomputation exactly matches the original result except
the relocated source path. G00–G06/G08/G09 are complete; G07 is not triggered.

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
| G05 terminal proposal and collection | `calibration/continuation-01/continuation-driver.json`, `calibration/run-02/journal/00009.json`, `proposed-gateway-service-formal.json`, `calibration/run-02-collection-verified.json` | Driver exit 0; terminal `proposed` / decision `complete`, no pending attempt; proposed ordinary/near/burst/overload rates 10,000/22,781/2,000/75,938; 705 hashes / 746,338,997 bytes verified; subsequent formal freeze recorded separately below |
| Source-bound correctness prerequisites | `formal/preparation-01/correctness-receipt.json`, `correctness-audit.md`, `artifact-index.json` | Five prerequisite categories audited against A/B sources and concrete test artifacts; platform/scope limitations retained; not a formal adoption or G09 receipt |
| G05 completed formal freeze | `formal/freeze-01/freeze.json`, `freeze-validation.json`, `gateway-service-formal.json`, `formal-plan.json` | Frozen at 16:19:55.525998Z; freeze SHA-256 `37646da98a7f6eda9fd287e22937c31869b5fe841d96bc931cd93bf82897f332`; validation receipt binds schema, source/binary and correctness gates before performance launch |
| G06 completed guarded run | `formal/run-01-driver.json`, `.log`, `formal/run-01/guard-report.json`, `formal/run-01/pairs/` | All 70 measurements and 14 warmups retained; driver ended 16:47:47.105786Z, runner exit 1, summarizer exit 0; 84 guard checks without a stop |
| G06 independent decision | `formal/run-01/independent-evaluation/gateway-evaluation.json`, `.md`, `validation/pair-report.json` | Valid reject / A; source unchanged; near CPU reduction 6.4025%, RTT p99 +13.7174%, scheduled-to-completion p99 +10.0948%; all 35 pairs and 14 warmups present |
| G06 collection | `formal/run-01/collection-sha256.json`, `formal/run-01-collection-verified.json` | 1,632 files / 3,736,738,350 bytes verified; original pair source tree SHA `818b47ebb46c8524b1c7c04f740cc64aa5abb126604b14bc35aa96010ba63905` |
| Final source/coverage bridge | `final/source-bridge-01/bridge.json`, `.md` | 54 unchanged C++/header inputs bridge existing A Debug/ASan-UBSan/TSan and extended correctness; 122-file code/fixture identity matches f6765b5; final combined Linux integration is recorded below |
| Final selected source | `final/final-source-binding.json`, `final-source.bundle` | Commit `4cb1cc5781d3d1bfa6c55128f8440ad83e282332`, clean batch1; same 122 executable/fixture files, complete Git bundle SHA recorded |
| G08 detailed tables and checks | `final/report-01/report-metrics.json`, `render_formal_report.py`, `doc-links-02.json`, `doc-anchor-check.json`, `external-links-01.json` | All 35 paired primary metrics checked; 103 Markdown targets checked, 10 fragments matched to headings, all four external URLs returned 200 |
| G09 fresh Linux driver | `final/linux-driver.json`, `.log`, `final/linux-01/result.json`, `A-release.xml`, `B-release.xml` | Exit 0; A full Release 136 passes / two default-disabled extended registrations, B network 15 passes; fresh B `b6ee3a9980073f774de6656d65a0b13a4b42bdcd` changes only the frame bound from 4cb1cc5 |
| G09 smoke and demo | `final/linux-01/core-smoke/`, `network-smoke/`, `*-recomputation.json`, `gateway-demo/` | Core and all seven network smoke rows/warmups passed; copy-backed summaries matched; two real clients verified seven commands/two identical cross-client Trades with request-ID reuse |
| G09 short replay | `final/short-driver.json`, `final/linux-01/short-01/evidence/result.json`, `short-01/pairs/` | One invocation: six pairs / 12 measurements + six warmups all passed; independent summary matched, raw source/binaries unchanged; calibration replay is not a replacement adoption matrix |
| G09 raw test and host collection | `final/linux-01/test-artifact-copy.json`, `test-artifacts/`, `A-deep-book/`, `final/linux-01-collection-verified.json` | 6,865 retained raw test artifacts copied without rerunning tests; complete final transfer verifies 8,302 files / 185,874,848 bytes; intentionally temporary fixtures retain JUnit/log evidence |
| Single verified raw archive | `build/gateway-final-archive-01/gateway-raw.tar`, `gateway-raw.tar.sha256`, `archive.json` (repository-relative directory, outside the evidence tree) | 5,675,490,816-byte tar; SHA `997b2edac92038b7aed1c4e2353cd67b56ad4eef1284756271313f0c88e6b2b2`; created/listed/extracted, final SHA unchanged; retained old VM backup excluded |
| Independent archive-copy formal result | `build/gateway-final-archive-01/recomputed/gateway-evaluation.json` (repository-relative) | Finished 17:15:26.620030Z, all archive commands exit 0; every evaluation value matches except relocated source path, including every pair, gates, source identities and valid reject/A decision |

See [execution plan](gateway_optimization_plan.md) for the completed dependency
map and [report](gateway_report.md#g09-clean-delivery-verification) for scope and
remaining limits. The raw archive preserves the tested source bundle and all
collected evidence; its later verification receipt and documentation closure are
retained outside it without rebuilding or replacing the archive.
