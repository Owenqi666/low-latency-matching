# M3 evidence index

The complete experiment rejects the sixteen-frame candidate and retains the
measured one-frame control. Paths below identify retained, source-specific
evidence. Final PR/main and archive identities are bound separately by the
[`m3-experiments` release acceptance record](https://github.com/Owenqi666/low-latency-matching/releases/download/m3-experiments/acceptance.json);
intermediate candidate checks do not substitute for those final gates.

## Sources and existing evidence

| Record | Identity and scope | Local evidence |
|---|---|---|
| Published M2 | `db9b74f4181a2dc4a50966c20080949c839bf73f`, `m2-service`; historical results retain their original source/environment | [M2 evidence index](m2_evidence_index.md) |
| Targeted M3 diagnosis | Clean M2, corrected loadgen, four diagnosed runs and four separate warmups; 203 copied original files verified by SHA-256 | `build/m3-diagnostics/`; [diagnostic report](m3_diagnostics.md) |
| Observed one-frame control | `7b8fcd3b074ed39ff24a3488253397e1dfb7094e`; M2 plus local send-queue extraction, matching observations and shared measurement tools | `build/m3-validation/control-final-local/` |
| Sixteen-frame candidate | `b1ba98c205de3bd717eb0f118fb9771d1f251a25`; only the selected frame constant differs from the control | `build/m3-validation/candidate-local/`; parent `source-binding.json` |
| Independent Linux builds | Both clean revisions passed 104 Release tests; existing pinned dependency sources reused | `build/m3-linux-validation/`; host checked 2,739 payload files per variant and reran JUnit/group checks |
| Candidate PR CI | [38988332237](https://github.com/Owenqi666/low-latency-matching/actions/runs/38988332237); tested merge `3fec7a70c07958f1706f8eec219948740bf8fbc9`, parents M2 main and candidate | `build/m3-ci/candidate-b1ba98c/inspection.json` and all four downloaded bundles |
| Formal A/B | 70 measured attempts and 14 warmups; 65 measured attempts deliver fully, all 84 drain and pass Reference; complete original/paired summaries pass | `build/m3-measurement/pair-run-1/`; 1,618 original files / 4,612,638,661 bytes pass copied-file hashes; host revalidation reproduces eight derived files byte-for-byte |
| Frozen adoption decision | Reject batch16: primary CPU benefit passes, single-client RTT p99 regression fails; restore production frame bound to 1 | `pair-run-1/adoption-assessment.json`, `build/m3-measurement/t05-review.json`; [report](m3_report.md) and [all pairs](benchmarks/m3_service_pairs.md) |
| Separate A/B profiling | One 45k/s diagnosis and warmup per variant; original exits/signals retained, reports decode successfully with zero lost samples | `build/m3-profiling/`; 114 original files / 383,944,643 bytes verified; host summaries byte-identical, `profile-assessment.json` records limits |
| Fresh Linux reproduction | Public clone at control `7b8fcd3`, fresh dependencies/build, 104 Release tests, two CLI clients and smoke; three short 45k pairs compare fresh A with retained B | `build/m3-clean-repro/collected/`; 3,269 selected files / 204,077,752 bytes verified; `host-revalidation/verification.json` confirms independent checks, eleven byte-identical derived files and only the core report's output-directory relocation |

The candidate CI inspection covers 103/104/103/103 tests without failure or
skip, all new send-queue tests and the paired test, actual multi-frame writes,
eleven corrupted-evidence cases and restoration, core smoke and all 14 network
smoke attempts. It is an intermediate candidate check, not final-main acceptance.

The formal run used two server binaries with SHA-256:

```text
control   dca59a4cd8027511b03e46da3b96658728ba74856531432597db9bf470a449b9
candidate 56100432a2791e2fda7a21031943d00eab328aa99e9c08e49e5e3cacb256122c
loadgen   9e9455a4c908c79f43fe7f7596522517999b1fb41a79eb0a322e300db0a18256
verifier  239ea89ea98faea32152e72f816f30a3b1c9583e4dbfb23d296d4512d7ed29bb
```

Both sides explicitly use the same candidate-built loadgen and verifier. Build
directory provenance, flags, actual source hashes and binary hashes are retained
in the manifests; a source identifier alone does not prove a binary's identity.

## Permanent delivery and verification

The measurement archive, `m3-measurements.tar.gz`, retains complete paired raw
data, failed attempts, diagnosis and separate profiling, source snapshots and
the control/candidate patch. The validation archive, `m3-validation.tar.gz`,
retains local/Linux checks, fresh-checkout reproduction, the identified binaries
and downloaded candidate/final-PR/main CI with independent inspections. Each
archive has `FILES.sha256` and `archive-manifest.json`, mapping the selected
local evidence paths to archive entries. Duplicate transport tar files are
excluded; their unpacked originals and copy-verification manifests are retained.

The release supplies `acceptance.json` and `SHA256SUMS`. Verify downloaded
assets with `sha256sum -c SHA256SUMS`, then use each archive's internal checksums.
The acceptance record names the latest tested PR checkout/parents, merged main,
its push CI, task mapping, source relationships, archive hashes and limitations.
Actions retention alone is insufficient. Publication is complete only after
those exact-source CI gates, archive verification and uploaded-asset checks pass.

Source archives must preserve the candidate even if it is rejected. Public
archives exclude dependency caches, build trees other than selected evidence
and identified binaries, Git internals, VM disks, SSH material and original
local project/task documents. Raw synthetic measurement inputs and failure
records remain available. Valid evidence, successful delivery and sufficient
samples are separate outcomes.
