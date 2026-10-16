# CI evidence

Recorded on 2026-10-16. This record covers the T00 build skeleton and its deliberate failure/recovery probe. It does not claim completion of the later M1 matching, differential, benchmark or T07 trace-artifact checks.

## Baseline, failure and recovery

The probe ran in a separate clone on `ci/failure-probe`; it was not merged into `main`.

| Stage | Commit | Actual GitHub Actions run | Observed result |
| --- | --- | --- | --- |
| Main baseline | `8c6d27d696b08730cf897e59bf3d21a892bef771` | [38968838643](https://github.com/Owenqi666/low-latency-matching/actions/runs/38968838643) | Debug, Release and ASan/UBSan configured, built and passed CTest. Each executed one `Contract.IntegerDomains` test. |
| Intentional failure | `9113e001aaf7b4ce8fb4c478a2e6fc7b015745c2` | [38969150821](https://github.com/Owenqi666/low-latency-matching/actions/runs/38969150821) | All three jobs built successfully and failed at CTest, exit code 8. All three failure-artifact upload steps succeeded. |
| Correct assertion restored | `a486fae8d352486db1436eba1b591f39063f1fcc` | [38969271348](https://github.com/Owenqi666/low-latency-matching/actions/runs/38969271348) | Debug, Release and ASan/UBSan all completed successfully. |

The baseline logs identify the actual runner image as `ubuntu-24.04`, image version `20261012.334.1`, and the C++ compiler as GNU 13.3.0. The baseline workflow selected `ubuntu-latest`, so this observation is specific to those runs rather than a guarantee for future runs.

The only injected defect changed the expected value in `tests/contract_test.cpp` from:

```cpp
EXPECT_EQ(std::numeric_limits<llmatch::Price>::digits, 63);
```

to `62`. The recovery commit restored `63`. A local `git diff 8c6d27d696b08730cf897e59bf3d21a892bef771 --exit-code` at the recovery commit returned zero: its final tree matches the baseline exactly.

## Failure artifacts actually downloaded

After the failed run completed, this command succeeded and downloaded all three artifacts:

```sh
gh run download 38969150821 \
  --repo Owenqi666/low-latency-matching \
  --dir /private/tmp/low-latency-ci-probe-20261016-artifacts
```

Each artifact contained `Testing/Temporary/LastTest.log`, `LastTestsFailed.log` and `CTestCostData.txt`. Every `LastTest.log` identified `Contract.IntegerDomains`, actual digits `63`, expected value `62`, and `Test Failed.` Thus the failure was the intended assertion, rather than a dependency or compiler failure.

SHA-256 values of the downloaded `Testing/Temporary/LastTest.log` files:

| Artifact | SHA-256 |
| --- | --- |
| `failure-debug` | `7c1f8fe18195e83257631f51062704c0d92ca1d82361f0716319e82c3a4661f3` |
| `failure-release` | `5e10594d249d661521146048fc36a4163056fd3a2496bb8f8432d7399cc7dd26` |
| `failure-asan-ubsan` | `9817c2a81910bfef5ecb4a2db2f7170112318977cb5dcd1bb385e51df7cfd92e` |

These are extracted-log hashes, not archive hashes. GitHub artifact retention is finite; the successful retrieval and inspected contents are recorded here independently of later artifact expiry.

## What this verifies

- [x] The initial CI executes real, nonempty CTest jobs in Debug, Release and ASan/UBSan configurations.
- [x] An incorrect expected value causes those jobs and the overall workflow to fail.
- [x] Failure logs are uploaded and can actually be downloaded and inspected.
- [x] Restoring the assertion makes the probe branch pass again.
- [ ] T07: verify a deliberately failing differential case uploads its actual trace, configuration and first-divergence report, then download and replay those artifacts.

The final unchecked item requires the later differential-test implementation; this initial assertion probe supplies no evidence for it.

## M1 workflow revision awaiting PR verification

The revised workflow adapts the clean-install, layered-verification and evidence-retention principles from [quant-ai-agent public-ci](https://github.com/Owenqi666/quant-ai-agent/blob/main/.github/workflows/public-ci.yml), inspected on 2026-10-16. It uses the C++ project's own presets and dependencies; it does not import that project's Python, Node or maintenance-source export steps.

- Triggers are PRs targeting `main`, pushes to `main`, and manual dispatch. A feature-branch push without an open PR does not trigger this workflow. Older runs of the same workflow/ref are cancelled.
- Debug, Release and ASan/UBSan matrix entries each use an independent `ubuntu-24.04` runner and build directory. `fail-fast: false` lets the remaining jobs finish when one fails. There is no shared build/dependency cache; CMake fetches GoogleTest using the checked-in version and archive hash.
- Each job records the actual checked-out SHA, OS, GNU C++ compiler, CMake and Ninja versions. On PR runs, the checked-out SHA may be GitHub's PR merge revision; `checkout-sha.log` records what was actually tested.
- Dependency installation, configure, build and CTest have separate steps and logs. Every shell step uses `set -euo pipefail`, so piping through `tee` does not hide a failed command. CTest uses `--no-tests=error`.
- Evidence uploads run with `always()`, including after a failed build or test. Artifact names are `ci-evidence-<preset>-<run_id>-<run_attempt>`, with 14-day retention. Uploads include `build/ci-evidence/<preset>/`, the configured `CMakeCache.txt`, CTest logs, and all files under `build/<preset>/failures/` for traces, configurations and divergence reports when produced.
- The Release benchmark smoke step is explicitly pending T08 tooling and report validation. No nonexistent benchmark command is invoked, and these jobs do not yet claim benchmark-smoke coverage.

The intended release sequence is: pass the feature PR's jobs, review and merge that PR, then verify the new `main` push run and its exact SHA. A passing pre-merge run does not by itself establish that the merged `main` revision passed.

Local static checks passed: YAML parsing, `bash -n` for all six shell steps, runner/preset mapping, and `git diff --check`. These checks do not replace executing the workflow on GitHub.

- [ ] Revised workflow passes on the feature PR with actual toolchain logs and downloadable evidence.
- [ ] T07 failure injection demonstrates a failed CI run with downloadable trace, configuration and first-divergence report; replay confirms the saved failure before restoring the code.
- [ ] The reviewed PR is merged only after its required checks pass.
- [ ] The resulting `main` SHA independently passes its post-merge workflow.

The earlier T00 run links remain historical evidence for the initial workflow; they do not validate this revision.
