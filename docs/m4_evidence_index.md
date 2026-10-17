# M4 evidence index

M4 retains the measured list control. The fixed-slot candidate misses the
frozen cancel-heavy throughput threshold. The [report](m4_report.md) and
[ADR 006](adr/006-fixed-order-storage.md) distinguish that decision from final
delivery. Final PR/main identities and publication are governed by the
`m4-order-storage` release's `acceptance.json` and post-upload
`publication-verification.json`; they are not established by intermediate
candidate checks.

## Source and evidence map

| Record | Identity and scope | Local evidence |
| --- | --- | --- |
| Accepted M3 | `37220e16fe0f05110c5f4ea112e4057bc55be122`, `m3-experiments`; historical results retain their original scope | [M3 index](m3_evidence_index.md), `build/m4-baseline/` |
| Frozen plan | `6b9233516e7573af7929f315b9f057d890fae29f`, before candidate implementation and formal timing | [Plan](m4_experiment_plan.md), [diagnostics](m4_diagnostics.md) |
| List control A | `97fdc6ee165201b0ab9b3997879f5296fb508d9f`; M3 production plus common tools and regressions | `build/m4-validation/control-source.json` |
| Fixed-slot candidate B | `4cf669ff2e932c6f27adeca0a9e143ffd03430b1`; only the two OrderBook files differ from A | `build/m4-validation/candidate-source.json` |
| Local checks | Each source passed 105 Debug and 108 Release tests, with discovery/JUnit and groups checked | `build/m4-validation/{control,candidate}-{debug,release}/` |
| Linux frozen builds | Each source passed 108 Release tests; clean sources, reused pinned dependency sources, not T06 fresh installation | `build/m4-linux-validation/guest/`, `host-validation.json`; 11,059 copied files verified |
| Candidate CI | [39050889184](https://github.com/Owenqi666/low-latency-matching/actions/runs/39050889184), 105/108/105/105 tests; actual tested merge `6f233a140e6a81619dd3660dc46ae84e1250103a`, parents M3 main and B | `build/m4-ci/candidate-4cf669f/inspection.json` and four original downloaded bundles |
| Formal core | Five scenes, 25 pairs, 100 timing intervals; all original inputs, Reference ledgers, warmups, samples and counters | `build/m4-measurement/core-run-1/`; 793 copied files; `core-host-revalidation.json` |
| Resource diagnostics | Three short scenes per source; allocation/lifetime, actual slot layout and instrumented constructor observations | `build/m4-storage-diagnostic/linux/`; 103 copied files; `linux-host-verification.json` |
| Formal service | Four scenes, 40 measured attempts and eight warmups; all deliver/drain/Reference, all formal sample targets pass; eight derived files reproduce byte-for-byte | `build/m4-measurement/service-run-1/`; 941 copied files; `service-host-revalidation.json` |
| Production selection | Working-tree production, build, tools, tests and inputs restored to A; final committed relation is recorded separately | `build/m4-delivery/production-selection.json`, final `source-relation.json` |
| Fresh Linux reproduction | New public A/B checkouts and dependencies; 108 selected-path Release tests, two real CLI clients, core/seven-scene network smoke and two short core pairs; independent checks passed | `build/m4-clean-repro/collected/`, `host-revalidation/verification.json`; 5,947 copied files / 56,766,037 bytes verified |
| Final PR/main and publication | Latest PR artifacts, normal merge, exact-main push artifacts, permanent archives and remote upload checks | `build/m4-ci/final-pr/`, `build/m4-ci/main/`, `build/m4-delivery/`; authoritative final identities in release receipts |

Source hashes and build provenance bind actual binaries to the frozen trees;
a Git SHA alone does not establish the executable used. Original guest paths
inside reports document provenance and can be relocated with the retained
tools. Independent recomputation uses a separate copy, preserving original raw
and derived files. Core report directory fields may relocate; any other change
must be explained rather than silently accepted.

## Permanent archive layout

The intended release assets are `m4-measurements.tar.gz` and
`m4-validation.tar.gz`, plus `acceptance.json`, `SHA256SUMS` and the publication
receipt. Their actual publication/verification status belongs to the release
record, not to the presence of this index in Git.

- Measurements: `measurement/core-run-1/`, `measurement/service-run-1/`, copy
  manifests, independent revalidation receipts, host environment and
  `diagnostics/{macos,linux}/`.
- Source: exact Git archives for M3, A, B and final main; full M3-to-A,
  A-to-B and A-to-final patches, source relation and binary identity index.
  The rejected B remains independently reconstructible.
- Validation: selected local/Linux evidence, clean reproduction, original
  candidate/final-PR/main CI downloads and independent inspections, final
  gates and delivery helpers.

Each archive contains `FILES.sha256` and `archive-manifest.json`. The latter
maps explicit local source paths to archive members. Duplicate transport tar
files are excluded; unpacked originals and their copied-file verification
manifests are retained. Original project/task documents, VM/SSH material,
dependency caches and unrelated build trees are excluded.

After downloading the published assets, first run `sha256sum -c SHA256SUMS`,
then check the archives' internal inventories with the retained
`validation/delivery/verify_archive.py`. Exact tag, asset byte size and GitHub
digest are checked after upload; the publication receipt closes those pending
items without rewriting the already hashed archives. Actions' 14-day retention
is not the permanent evidence store.

Reproduction commands are in [core methodology](benchmark_method.md#paired-m4-order-storage-comparison)
and [service methodology](service_benchmark_method.md#m4-service-regression-subset).
Formal data, functional smoke, diagnostic allocation requests and whole-process
RSS retain distinct meanings throughout the reports.
