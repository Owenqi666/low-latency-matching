# M2 evidence index

The [M2 release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m2-service)
is the publication record. Its `acceptance.json` binds the final PR head and
actual tested checkout, merged main SHA, successful main push run, downloaded
artifact inspections and archive hashes. This avoids embedding a document's own
future commit SHA in that document. Publication is gated on those checks;
intermediate results below are not a substitute for the final release record.

## What each record establishes

| Question | Record |
|---|---|
| Contracts and fixed bounds | [Protocol](protocol.md), [architecture](service_architecture.md), [semantics](semantics.md), ADR [003](adr/003-pausable-service-output.md) / [004](adr/004-connection-identity-and-delivery.md) |
| Required implementation and checks | [M2 acceptance mapping](m2_acceptance.md), [progress](progress.md) |
| Real remote failure and recovery | [CI evidence](m2_ci_evidence.md): injected BBO watermark defect, all four failed jobs downloaded, actual TCP replay, restored four-job run and replay |
| Service correctness at scale | [Long validation](m2_long_validation.md): 120,000 measured commands, actual-admission replay, setup and warmups separate |
| Fresh Linux installation and demonstration | [Clean checkout](m2_clean_checkout.md), [walkthrough](service_walkthrough.md): fresh dependency downloads, CLI clients, slow-peer isolation, short benchmarks |
| Measurement boundaries and rate choices | [Method](service_benchmark_method.md), [all calibration attempts](m2_rate_selection.md) |
| Formal results | [M2 service report](m2_report.md), [core report](m2_core_measurements.md), [separate profiling](m2_profiling.md) |
| Final source and CI | Release `acceptance.json` and `validation/ci/final-pr`, `validation/ci/main` in the validation archive |

## Permanent release assets

| Asset | Contents |
|---|---|
| `m2-measurements.tar.gz` | Frozen formal matrix and every attempt; both calibration batches; core rounds and clock probes; profiling attempts, raw perf data and assessments; measured tracked source snapshots |
| `m2-validation.tar.gz` | Recorded Linux development and fresh-checkout evidence, 120,000-command long validation, local lifecycle follow-ups, downloaded intermediate/final PR and main CI artifacts and independent inspections |
| `m2-ci-probe-evidence.tar.gz` | Controlled failure/recovery artifacts, downloaded-trace reproductions, baseline/fault/restored tracked source, one-line fault patch and checksums |
| `acceptance.json` | Final source identities, CI URLs and conclusions, inspection results, explicit measurement limitations, archive sizes and SHA-256 |
| `SHA256SUMS` | SHA-256 for the three archives and acceptance record |

The two main archives include `FILES.sha256` for their payload files and
`archive-manifest.json` for source-to-archive mappings. The existing probe archive
has its own file manifest. Preserve these assets beyond the 14-day Actions
retention period. Ordinary source code is also available at the release tag;
measurement source is separately retained because later reports do not change
its production binaries.

## Archive paths and local evidence

The archive prefixes below are fixed; local build paths in detailed reports
identify where evidence was originally produced, not additional prerequisites.

| Archive location | Original local source |
|---|---|
| `measurement/m2-formal-eb0a109/` | Corrected formal matrix under `build/m2-measurement/m2-formal-eb0a109/` |
| `measurement/m2-formal-f58ff79/` | Prior matrix retained with its plan-initialization defect; `build/m2-measurement/m2-formal-f58ff79/` |
| `measurement/m2-calibration-ladder/`, `measurement/m2-calibration-refine/` | Same names under `build/m2-measurement/` |
| `measurement/core-run-1/`, `measurement/core-transition/`, `measurement/core-manifests/` | Core raw results, source/binary transition and fixed input manifests under `build/m2-measurement/` |
| `measurement/host-environment.json` | `build/m2-measurement/host-environment.json` |
| `profiling/` | `build/m2-profiling/`, including both attempts and their actual exit states |
| `source/source-f58ff79.tar.gz`, `source/source-eb0a109.tar.gz` | Tracked core/earlier network source and corrected formal network source |
| `validation/linux-development/` | `build/m2-vm/evidence/dirty-validation-20261016T230725Z/` |
| `validation/linux-clean-ce9e94f/` | `build/m2-vm/evidence/clean-ce9e94f/` |
| `validation/linux-identity-restart/` | `build/m2-vm/evidence/followup-identity-restart-85de7f3/` |
| `validation/service-long/` | `build/m2-long-service/run-1/` |
| `validation/local-followup/` | Focused lifecycle/TCP records and final local 95-entry Debug suite |
| `validation/ci/initial-pr/`, `gateway-timestamp-pr/`, `lifecycle-pr/`, `loadgen-schedule-pr/` | Downloaded CI at `ce9e94f`, `85de7f3`, `f58ff79`, `eb0a109`; exact tested merge SHAs in inspections |
| `validation/ci/final-pr/`, `validation/ci/main/` | Latest accepted PR and post-merge main downloads, named by `acceptance.json` |

All formal warmups and measured rounds are retained, including request failures.
The original guest report is kept alongside the downloaded independent recheck.
The result's `evidence_valid` describes consistency; `all_runs_succeeded` describes
request success. A valid lossy run does not establish stable capacity. Raw
per-command hashes complement, rather than replace, the small full-event and
routing comparisons.

Archives exclude dependency caches, build trees, VM disks, SSH material, Git
internals and original local
planning/task documents. Public tests and synthetic inputs require no private
service or account. Linux VM loopback measurements describe the recorded shared
host, not bare-metal, cross-machine or production-market performance.
