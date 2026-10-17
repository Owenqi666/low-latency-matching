# M2 controlled CI failure and recovery evidence

Recorded on 2026-10-17 (Europe/London). This is the M2 T08 controlled failure,
artifact retrieval and reproduction record. It does not establish that a later
PR, merged `main` revision or release passed, and contains no performance claim.

## Revisions and actual runs

The experiment used the isolated clone `build/m2-ci-fault` and branch
`test/m2-ci-failure-probe`, starting from
`ce9e94f134f6d9894f67922586004c7650a32467`. Neither probe commit was proposed for
merge. The primary worktree's branch and source were not changed by this probe.

| Stage | Complete commit SHA | Manual GitHub Actions run | Result |
| --- | --- | --- | --- |
| Injected BBO defect | `e7e8f0d740cf6b098d356f63c6a2258728864b07` | [38980208331](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980208331) | All four jobs failed their test step and uploaded artifacts. |
| Correct code restored | `6580d98749b46c92e20cbcd946be9e390254acaa` | [38980587123](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980587123) | All four jobs passed and uploaded artifacts. |

Both events were `workflow_dispatch`. Every downloaded job's `checkout-sha.log`
equals its corresponding complete SHA above. At the restored revision,
`git diff ce9e94f134f6d9894f67922586004c7650a32467 --exit-code` returned zero:
the entire tracked tree matches the baseline.

The single injected source change in `MatchingServer::route` was:

```diff
-        cached_bbo_ = std::get<Bbo>(message);
+        cached_bbo_ = std::get<Bbo>(message); ++cached_bbo_.as_of_event_seq;
```

It corrupts the BBO event watermark while leaving the matching results and
command sequence unchanged. The restoration removed only that increment.

## Downloaded job evidence

All eight artifacts were actually downloaded with `gh run download`, four from
each run. Their indexes, GitHub-reported digests, expiration timestamps and
extracted contents are retained under `build/m2-ci-failure-evidence/`.

| Preset | Discovered/executed tests | Fault run failures | Restored run failures / skips |
| --- | ---: | --- | --- |
| Debug | 93 | `service_integration`, `service_evidence` | 0 / 0 |
| Release | 94 | `service_integration`, `service_evidence` | 0 / 0 |
| ASan/UBSan | 93 | `service_integration`, `service_evidence` | 0 / 0 |
| TSan, Clang 18 | 93 | `service_integration`, `service_evidence` | 0 / 0 |

These are observations of these revisions, not fixed-count acceptance rules.
The restored run's downloaded discovery JSON and JUnit were independently rechecked with the
probe revision's `check_test_groups.py`; every required group was nonempty and
the restored execution had no failed, missing or skipped discovered tests.

The first failing step in Debug, Release and ASan/UBSan was **Run all discovered
tests and retain JUnit results**; for TSan it was **Run the full suite under
TSan**. The later execution-group checker also failed, as intended. Configure
and build succeeded. The downloaded TSan test log contained neither a TSan
runtime fatal error nor a TSan race report; its failure was the same semantic
test failure as the other jobs.

In every failed job, `service_evidence` saved `network-actual.json`,
`network-expected.json`, `admitted.trace`, `engine.config`, `final.snapshot`,
per-client wire logs and server records. The complete network/reference
comparison failed at `self.assertEqual(actual, expected)`:

- The server exited successfully and admitted/completed all 18 commands.
- Exactly 31 received BBO messages differed, solely in `as_of_event_seq`.
- The first mismatch was client 1, message index 3: actual `3`, expected `2`.
- The restored run's corresponding complete network streams matched their
  independent Reference results in all four jobs.

Thus the negative test detected the injected content error, rather than a
compiler, startup, timeout or missing-artifact failure.

On the restored Release job, the core benchmark smoke, bounded network smoke
and separate network evidence-check step all passed. Its downloaded network
manifest records clean commit `6580d98749b46c92e20cbcd946be9e390254acaa` and all
14 declared attempts completed (seven warmups and seven measurement attempts).
A copy of those downloaded files was checked again locally with the independent
service summarizer; it returned zero. Raw downloaded artifacts were preserved.

## Intermediate feature-PR checks

Separate downloaded-artifact inspection records four passing feature-PR stages:

| PR head | CI run | Actual tested PR merge checkout |
| --- | --- | --- |
| `ce9e94f134f6d9894f67922586004c7650a32467` | [38980042883](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980042883) | `09f7f5a8401ca655f26ccd7b87263e8509a510b1` |
| `85de7f3262bc96a8ff889226592282cee1c57684` | [38980514661](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980514661) | `e89db5f5a217953e967cb4d3ca2b37281bb76d66` |
| `f58ff79d49fd08c2bcb399ad989eb47ed0830a40` | [38981810190](https://github.com/Owenqi666/low-latency-matching/actions/runs/38981810190) | `f370b4e63a366556ba00cba116fc254e6ce296a1` |
| `eb0a109b026c8ac9cf48d987163fad8751980047` | [38983432078](https://github.com/Owenqi666/low-latency-matching/actions/runs/38983432078) | `a4bcf6612769b95c17961e1313c49c33bed5a598` |

The first two stages executed 93 Debug, 94 Release, 93 ASan/UBSan and 93 TSan tests,
without failures or skips. The later stage's downloaded network smoke also
passed independent summarization for all 14 declared attempts. The inspection
record is `build/m2-measurement/pr-ci-inspection.json`; a copy is retained with
this probe's archive materials. These PR merge checkouts differ from the head
commits and must not be relabelled as tests of those head SHAs alone. The final
feature PR and post-merge `main` are separately bound in release `acceptance.json`
after all report changes pass the same publication gates.

The third stage includes the added partial-sweep abort, Gateway exception and
restart tests: 95 Debug, 96 Release, 95 ASan/UBSan and 95 TSan entries passed with
no failures or skips. All four downloaded jobs observed Linux descriptor 9 being
reused with ClientId changing from 1 to 2. The downloaded Release network smoke
was independently checked again: all 14 declared attempts succeeded. Its retained
inspection is `build/m2-ci-f58ff79/inspection.json`; all downloaded files are in
the [permanent validation archive](m2_evidence_index.md).

The fourth stage removes plan-sized initialization from the load generator's
measured window. All four jobs again passed 95/96/95/95 tests with no failures
or skips. Downloaded artifacts were independently checked for required groups,
actual descriptor reuse, the 14-attempt network smoke and core smoke. The record
is `build/m2-ci-eb0a109/inspection.json`. Its source is the corrected formal
network measurement revision; subsequent report-only changes must still pass
the final PR and main gates identified by the release.

## Actual local reproduction from the downloaded trace

The Debug failure artifact's downloaded `admitted.trace` was executed twice on
macOS arm64, using separately configured clean Debug build directories in the
isolated clone. The local builds explicitly reused the already verified Boost
header source cache; they were not fresh dependency downloads. GitHub jobs
performed the clean dependency installation and configuration.

`reproduce_downloaded_trace.py` reads the downloaded commands, recreates the
three clients and their recorded join points, sends each request over real TCP,
and compares newly received frames to the downloaded independent Reference
expectation. It also runs the Reference replay CLI on the downloaded trace and
checks its final snapshot. It does not merely compare two stored JSON files.

| Local build | Same downloaded input | Newly received wire result | Independent Reference snapshot |
| --- | --- | --- | --- |
| Fault commit `e7e8f0d…` | 18 commands, new admitted trace byte-identical | Reproduced all 31 differences; new actual streams equal the downloaded CI actual streams; process check exited 1 | Matches |
| Restored commit `6580d987…` | The same 18 commands, new admitted trace byte-identical | Zero differences from Reference; process check exited 0 | Matches |

Both servers exited zero and completed all 18 commands. The second row replays
the **same downloaded failure input against restored code**; it is not a second
fault injection. Command arrays, source revisions, binary SHA-256 values, input
SHA-256 values and new wire logs are saved in the reproduction records.

Useful integrity anchors for that downloaded test case:

| File | SHA-256 |
| --- | --- |
| `admitted.trace` | `6649ba59e227e8baa746549ca6183a2b0abba3bdc0830aaa60595642d5d4bab0` |
| `network-actual.json` (fault) | `dc7721ccd46259186e555945be3186797719ccebf87d3e01ff07248045a2d5eb` |
| `network-expected.json` | `bba5b079c4cc98c171fee8121fa1419d4505dee49de35409109d712d100dd7e5` |
| `final.snapshot` | `b241070b59c0ff7dba8cd5a53096bad305fb4e0bd812056c59d589f02272b207` |

To repeat in a new output directory, check out one of the complete SHAs above
in a fresh clone and build `matching_server` and `replay` using CMake Debug with
`BUILD_TESTING=OFF`. From the repository containing the extracted evidence:

```sh
python3 build/m2-ci-failure-evidence/reproduce_downloaded_trace.py \
  --source /path/to/fresh-clone \
  --evidence build/m2-ci-failure-evidence/fault-artifacts/ci-evidence-debug-38980208331-1/debug/service-artifacts/evidence-full-network-6grqj418 \
  --server /path/to/fresh-clone/build/repro/matching_server \
  --replay /path/to/fresh-clone/build/repro/replay \
  --output /path/to/new-reproduction-directory
```

Expected exit status is 1 for the fault revision and 0 for the restored
revision. The recorded `*-command.json` files retain the exact commands
actually executed locally, including configure and build commands.

## Archive contents and boundaries

The local archive-ready directory is `build/m2-ci-failure-evidence/`:

- `probe.json`, `fault-run.json`, `restored-run.json`: revisions, run URLs,
  event, job conclusions and steps.
- `pr-ci-inspection.json`: the separate intermediate-PR inspection summary;
  its raw PR artifacts remain outside this controlled-probe bundle.
- `fault-artifacts/`, `restored-artifacts/` and their index JSON: all eight
  downloaded job artifacts, including logs, JUnit, configuration, traces,
  wire streams, snapshots and smoke records.
- `fault-validation.json`, `restored-validation.json`,
  `restored-revalidation/`: checkout, test-group, semantic and smoke checks.
- `reproduced-fault-from-ci/`, `reproduced-restored-from-ci/`, reproduction
  script, command JSON and logs: both actual local TCP/reference reproductions.
- `source-baseline.tar`, `source-fault.tar`, `source-restored.tar`, `fault.patch`:
  tracked source snapshots and the single-line fault, without a Git database.
- Local configure/build commands, logs and environment record; per-file
  checksums and an archive manifest bind the retained materials.

The archive excludes the isolated clone's `.git`, build trees, dependency
caches, local VM files, SSH keys and the original local project/task documents.
The source tar files were checked for these exclusions. The preliminary local
script check, which preceded the CI download, is kept separately in the working
evidence directory and excluded from the durable bundle.

GitHub artifact retention for these runs ends on 2026-10-30 UTC. Local retrieval and validation are complete. The [M2 evidence index](m2_evidence_index.md)
maps this retained probe bundle to its permanent release asset; final publication
and merge identities are recorded by the release acceptance record.
