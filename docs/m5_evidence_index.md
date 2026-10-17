# M5 evidence index

This index binds the [report](m5_report.md),
[all interval records](benchmarks/m5_itch_rounds.md) and
[reproduction instructions](m5_reproduction.md) to retained evidence.
Paths below identify the current workspace evidence; the planned permanent
mapping is listed at the end and the frozen manifest will confirm it. Historical raw
input and detailed real order/depth CSVs are local-only while redistribution
permission is unconfirmed. Their identities and permitted summaries are public.

At preparation, the measured candidate, T06 and candidate CI inspection were
complete. Final report-integrated PR checks, normal merge, exact-main push CI,
archive publication and downloaded-asset verification remained pending. The
final acceptance/publication receipts, rather than this pre-publication
document, identify the eventual delivered main and asset hashes.

## Source and build identities

| Evidence role | Recorded identity |
| --- | --- |
| Accepted M4 baseline | `9314cf077c3968d484c627aa1d7f7e51dfa28463`, tag `m4-order-storage` |
| Formal measurement and fresh Linux T06 | Clean public commit `7cea5df6d25c69a99831ed6b00a1babbbf151052` |
| Candidate PR head | `7cea5df6d25c69a99831ed6b00a1babbbf151052` |
| Candidate tested merge checkout | `53dbc147e772f25815d4412577e122829f6ce86e`; parents are the M4 baseline and the candidate head above |
| Linux `bench_itch` SHA-256 | `35225c62c36f1406d6f1ed2f958d6dc2f568c4345cce635c2e2e1ea2e41bf67f` |
| Linux `itch_replay` SHA-256 | `d122c1c625b758923595368f5c001f4cbe8b3b03e59b1eaa3c1bbda34ebafadf` |
| Current local macOS Release real-negative replay binary SHA-256 | `a619dae24b23a8cd8bd2deb79f2724485ced31a968333c2e460c7c99fc43718c` |
| Final merged/publication identity | Pending at preparation; use the final acceptance and publication receipts |

`m5-formal/build-evidence/source.json`, `CMakeCache.txt` and
`compile_commands.json` preserve the source-file hashes, dirty-state check and
actual compiler inputs. `matrix-manifest.json` binds those files, both binaries,
the archived tool copies, each input, verification receipt and interval.
T06's `run.json` independently records its checkout and produced binaries.
No old CI success is transferred to a later report or main commit. The final
delivery must also record the relation between measured/reproduced source and
the eventual publication source; that relation is not assumed here.

## Correctness and reproduction evidence

| Claim | Retained evidence | Scope |
| --- | --- | --- |
| Independent byte contract | `data/itch/golden.hex`, `golden.bin`, `golden_expected.json`; [hand calculation](../data/itch/README.md) | Hand-written bytes and expectations; nine target updates across 18 messages |
| Original-byte reference | `reference/itch_reference.py`, `scripts/verify_itch.py` | Independent decode/order dictionary; per-update affected orders/levels/BBO, full checkpoints/final state and saved-output comparison |
| Early local long check | `build/m5-python-long/workload/workload.json`; `build/m5-python-long/cmake-release-verification/verification.json` | 150,000 messages, 120,000 compared updates, 12 checkpoints; preserves its own historical binary/tool hashes |
| Current measured-source long coverage | `build/m5-measurement/collected/m5-formal/verification/{mixed,cancel_replace,multilevel}/verification.json` | Each input: 800,000 compared updates, 80 checkpoints and final state, before any timed process |
| Historical acquisition provenance | `build/m5-data/real-prefix-1/capture.json` | URL/date, response identity, bounded compressed consumption, retained-prefix identity and cutoff; not a whole-file integrity claim |
| Historical replay on fresh source | `build/m5-clean-repro/collected/itch-real/verification.json`; `run.json` | 1,000 AAPL updates, four checkpoints, final state; same saved input, `acquisition_repeated=false` |
| Representative real overdraw and saved-command replay | `build/m5-data/real-negative-1/mutation.json`; `build/m5-local/real-negative-final/verification.json`, `replay/error.json`, `failure-replay/verification.json`, `expected-failure-check.json` | Current tools rejected E at offset 10,286,348; the saved verifier command was actually executed and reproduced exit 1, input identity and reference 194645; raw mutation stays local |
| Corrected failure replay contract | `tests/itch_cli_test.py`; `build/m5-clean-repro/test-artifacts/itch-cli/` and downloaded candidate CI `itch-cli` evidence | 41 cases per CLI suite; full/prefix, capacity and comparison failures retain exact input/options and are actually replayed |
| Fresh Linux dependencies/build/tests | `build/m5-clean-repro/collected/run.json`, `configure.log`, `build.log`, `CMakeCache.txt`, `compile_commands.json`, `test-discovery.json`, `ctest.xml`, `test-execution-check.json` | New public checkout/dependencies/build; 124 discovered and executed Release tests, nine required groups; clean source afterward |
| Two actual service clients | `build/m5-clean-repro/collected/two-clients/` | Seven commands, matching two-trade observations, completion/BBO checks and independent service verification |
| Smoke and negative demonstrations | `build/m5-clean-repro/collected/{core-smoke,network-smoke,itch-smoke,itch-golden,itch-negative}/`; `build/m5-clean-repro/test-artifacts/` | Existing core and seven network scenes, synthetic ITCH, retained negative/test artifacts |

The early long-check and original real-negative receipts predate the verifier failure
command correction; they remain historical evidence with their original tool
hashes. Their recorded successful comparisons and concrete overdraw rejection
are not rewritten; the original negative remains under
`build/m5-local/real-negative-verify-1/`. The later real-negative check uses
verifier SHA-256 `fa8fe5572dd4c9bd022ad7f404544bf32073bdb958c04d4f44d020c4bd0edd28`
and the local Release binary identified above. Its saved-command replay again
compared 139 updates before the same failure, and the expected-failure check
passed. The measured-source long checks and T06 also use the corrected
verifier. Its failure replay retains original input bytes, original mode and
resource/checkpoint settings, and reruns the independent verifier rather than
only the C++ CLI.
The early local long-check is supporting historical evidence; the complete
formal three-by-800,000-update checks provide the measured-version long
validation retained in the permanent measurement archive.

## Input identities

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| Independent golden | 553 | `2d7eb0a1ac701798e87eb532182bc0ee251f6a426410c0e63e1d5fc1525257e6` |
| Early `long_verify` | 4,937,909 | `a245b017fad2d85d38a151fc26534f08b2d5ec0f1b4f6c6e3750d04ec9f15847` |
| Formal mixed | 32,865,084 | `1e3b7e99263a73519a9c135c30c0f45bc04f43b0ddae33cb18689dd3afb07c0a` |
| Formal cancel_replace | 32,580,697 | `19551f5f940421419bf0954ec1d186519b3e0b6b6a747dc62f6a71ec8123625b` |
| Formal multilevel | 32,519,585 | `29888235b20fcab2fe96616011e76c4afc88f96ffc9a3a18cf89a91be8012519` |
| Real day-start AAPL prefix, local raw | 30,262,428 | `90bb246d6f9902c498765ed98a68784db45f5e21e4ae9a07c5513d7f1c364ad4` |
| Real overdraw prefix, local raw | 10,286,381 | `4c66c98905a5637f05cfba6c0b80bf64b6dd1c45dac05c0990ec520ef3d609a3` |

Synthetic `workload.json` files record seeds, requested and actual type counts,
capacity, observed occupancy, price scale and deterministic best-level removal
counts. Input SHA-256 binds the bytes; semantic comparison is separate. The
CLI/benchmark FNV-1a identity is a lightweight checksum, not a substitute for
SHA-256 or reference validation. Keep one authoritative input per workload.

## Measurement and CI receipts

The formal root is `build/m5-measurement/collected/m5-formal/`:

- `matrix-manifest.json`: complete plan and execution status, 30 measured
  intervals plus six warmups, actual source/build/tool/input identities.
- `inputs/*/workload.json` and `verification/*/verification.json`: generation
  and full original-byte reference checks before timing.
- `runs/<scenario>/<decode|rebuild>/<warmup|round_N>/result.json` and
  `benchmark.log`: all interval values and excluded output-write timing.
- `report.json` and `report.md`: derived five-round statistics and retained
  per-interval fields. `build/m5-measurement/independent-summary.log` records
  a separate local recomputation passing on the copied evidence.
- `build/m5-measurement/collected/m5-real-resource.json` and
  `build/m5-measurement/driver.log`: the single historical-prefix observation
  and its output-write timing; not another formal matrix.

Candidate [Actions run 39063078708](https://github.com/Owenqi666/low-latency-matching/actions/runs/39063078708)
is inspected in `build/m5-ci/candidate-39063078708/inspection.json`, alongside
the downloaded artifacts and independent revalidation outputs. It records
Debug/Release/ASan-UBSan/TSan discovery and JUnit counts of 120/124/120/120,
required groups, retained/independently replayed negatives, smoke re-summaries
and candidate head/base/merge-checkout relationships. The inspector's own hash
is recorded as a local post-CI tool; it is not claimed to have run in that
tested CI checkout. Final latest-PR and exact-main receipts are separate gates.

## Planned permanent assets

The planned release tag is `m5-itch-reconstruction`. The following names are
the intended layout, not a claim of completed publication. Actual asset sizes,
digests, archive membership, downloaded bytes and tag target must come from
the frozen release manifest and post-publication receipts.

| Planned asset | Purpose |
| --- | --- |
| `source-final.tar.gz` | Rebuildable final public source, tools and synthetic fixtures |
| `m5-measurements.tar.gz` | `formal/` holds the complete synthetic matrix; `real/capture.json`, `real/verification.json` (T06 source), `real/resource.json` and `real/negative/` hold permitted historical summaries |
| `m5-validation.tar.gz` | `t06/`, `t06-test-artifacts/`, final `ci/pr/` and `ci/main/`, `source-relation.json`, `local-release/` and `baseline/`; no real raw/order/depth files |
| `SHA256SUMS` | External checksums after archive contents and internal manifests are frozen |
| `acceptance.json` | Final source/PR/main identity and acceptance evidence, interpreted together with the subsequent publication receipt |
| `publication-verification.json` | Post-publication tag/assets/download/replay receipt; does not hash itself |

`real/negative/` maps the original authoritative `mutation.json` together with
the current `verification.json`, `error.json`, `expected-failure-check.json`
and the actually executed replay's `saved-command-verification.json`; it
contains metadata only, not the original or mutated raw bytes.

`t06/` excludes the historical replay's order/depth CSVs. Final `ci/pr/` and
`ci/main/` preserve the actual downloaded artifacts, inspections and independent
revalidation logs. Candidate-run inspection/run/parent summaries remain
historical context; the final two CI runs provide the final T03/T07 evidence.
The real-prefix resource JSON does not contain output-write duration; that value
comes from the retained driver log, whose archive location is specified by the
frozen manifest.

Publication must target the accepted merged main and be checked through actual
downloaded asset bytes, including archive replay. If the publication receipt
is uploaded, its upload is checked by one independent local final-state record.
These final acceptance, publication and final-state receipts are the authority
for T07/T08 completion; the preparation-time status in this report is historical.
Do not create recursive receipts or change frozen archive contents to include
their own later audit. Temporary Actions retention is not permanent evidence.
Do not archive VM disks, credentials, dependency caches, local original
planning documents, historical raw input or real order/depth CSVs.
