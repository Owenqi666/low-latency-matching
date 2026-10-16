# CI evidence

Recorded on 2026-10-16. This record covers the T00 build skeleton and its deliberate failure/recovery probe. It does not claim completion of the later M1 matching, differential, benchmark or T07 trace-artifact checks.

## Baseline, failure and recovery

The probe ran in a separate clone on `ci/failure-probe`; it was not merged into `main`.

| Stage | Commit | Actual GitHub Actions run | Observed result |
| --- | --- | --- | --- |
| Main baseline | `8c6d27d696b08730cf897e59bf3d21a892bef771` | [38968838643](https://github.com/Owenqi666/low-latency-matching/actions/runs/38968838643) | Debug, Release and ASan/UBSan configured, built and passed CTest. Each executed one `Contract.IntegerDomains` test. |
| Intentional failure | `9113e001aaf7b4ce8fb4c478a2e6fc7b015745c2` | [38969150821](https://github.com/Owenqi666/low-latency-matching/actions/runs/38969150821) | All three jobs built successfully and failed at CTest, exit code 8. All three failure-artifact upload steps succeeded. |
| Correct assertion restored | `a486fae8d352486db1436eba1b591f39063f1fcc` | [38969271348](https://github.com/Owenqi666/low-latency-matching/actions/runs/38969271348) | Debug, Release and ASan/UBSan all completed successfully. |

The baseline logs identify the actual runner image as `ubuntu-24.04`, image version `20261012.334.1`, and the C++ compiler as GNU 13.3.0. The workflow selects `ubuntu-latest`, so this observation is specific to these runs rather than a guarantee for future runs.

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
