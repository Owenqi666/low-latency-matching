# M2 clean Linux checkout reproduction

On 2026-10-16 UTC, Codex subagent `/root/baseline_core` reproduced commit
`ce9e94f134f6d9894f67922586004c7650a32467` in a new Linux checkout. Release
passed all 94 discovered CTest entries, a separate two-CLI demonstration,
seven short network workloads and a slow-peer demonstration. This establishes
reproduction of that source revision; final PR/main verification and release
remain separate gates in [M2 acceptance](m2_acceptance.md).

## Source and environment

The repository was cloned from
`https://github.com/Owenqi666/low-latency-matching.git` into
`/home/m2/llmatch-clean-ce9e94f`, then detached at the commit above. Both recorded
`git status --porcelain=v1` outputs are empty. The directory and its Release
build did not exist before this attempt. No dependency source override, old
build output, unpublished fixture or private service was used.

| Property | Recorded value |
|---|---|
| Guest | Ubuntu 24.04.5 LTS, aarch64, Linux 6.8.0-142-generic |
| Virtualization | QEMU 11.1.2 with macOS HVF acceleration; not bare metal |
| Assigned resources | 4 vCPUs, 4096 MiB RAM, 12 GiB virtual disk; no guest swap |
| Compiler | GNU C++ 13.3.0; Release `-O3 -DNDEBUG`, C++20, sanitizers off |
| Tools | CMake 3.28.3, Ninja 1.11.1, Python 3.12.3 |
| Parallelism | Build: 2; CTest: 1 |
| Network | Same-guest TCP loopback; port 0 and observed READY signal |
| Environment capture | 2026-10-16T23:15:02 UTC; disk free after verification: 4.7 GiB |

Fresh configuration downloaded, verified and extracted Boost 1.89.0 and
GoogleTest 1.17.0 in 31.3 seconds. Their archive SHA256 values were:

```text
Boost:      85a33fa22621b4f314f8e85e1a5e2a9363d22e4f4992925d4bb3bc631b5a0c7a
GoogleTest: 65fab701d9829d38cb77c14acdc431d2108bfdbf8979e40eb8ae567edf10b27c
```

`first-configure.log` contains the actual download/verification/extraction
steps. The saved CMake cache has empty `FETCHCONTENT_SOURCE_DIR_BOOST` and
`FETCHCONTENT_SOURCE_DIR_GOOGLETEST` values. This was a fresh source/build
checkout on an already provisioned Linux VM, not a claim that compiler and OS
package installation was repeated from a new VM image.

## Commands and observed results

These are the recorded build/test commands, with evidence paths relative to
the checkout. Configuration/build/test output was retained in separate logs.

```sh
git clone https://github.com/Owenqi666/low-latency-matching.git /home/m2/llmatch-clean-ce9e94f
cd /home/m2/llmatch-clean-ce9e94f
git checkout --detach ce9e94f134f6d9894f67922586004c7650a32467
mkdir -p build/t10-evidence
cmake --preset release -DFETCHCONTENT_QUIET=OFF
cmake --build --preset release --parallel 2
export CTEST_PARALLEL_LEVEL=1
export LLMATCH_SERVICE_ARTIFACTS="$PWD/build/t10-evidence/service-artifacts"
ctest --preset release --show-only=json-v1 > build/t10-evidence/discovery.json
python3 scripts/check_test_groups.py --discovery build/t10-evidence/discovery.json
ctest --preset release --output-on-failure --no-tests=error \
  --output-junit "$PWD/build/t10-evidence/results.xml"
python3 scripts/check_test_groups.py --discovery build/t10-evidence/discovery.json \
  --junit build/t10-evidence/results.xml
```

All 94 entries passed in 7.90 seconds; discovery and JUnit validation found no
missing, failed or skipped tests. This includes the deterministic
`ServerLifecycle.CoalescedWorkerDoneFinishesAtPumpRearm` regression, real TCP
integration, full-event service evidence, CLI, loadgen, service evidence
corruption checks and the Release-only core benchmark pipeline check. A CTest
entry can contain multiple Python scenarios; 94 is not an assertion count.

The separate demonstration used two actual `matching_client` processes against
`matching_server`, with event capacity 1 and command capacity 2. Seven commands
reused RequestId 7 and covered resting orders, two cross-client trades,
NotOwner, cancellation and IOC remainder. Both clients received identical
Trade records, BBO preceded the relevant Complete, and both ended with zero
pending requests. The server drained all seven commands and the independent
Reference verifier passed. The exact orchestration script, stdin commands and
both complete JSONL outputs are retained in the evidence bundle; the public
[walkthrough](service_walkthrough.md) provides the interactive procedure.

The short workload and separate slow-peer commands were:

```sh
python3 scripts/run_service_bench.py --server build/release/matching_server \
  --loadgen build/release/loadgen --verifier build/release/verify_service \
  --manifest data/workloads/service-smoke.json --commands 130 --rounds 1 \
  --output-dir build/t10-evidence/network-smoke
python3 scripts/summarize_service_bench.py build/t10-evidence/network-smoke
LLMATCH_SERVICE_ARTIFACTS="$PWD/build/t10-evidence/slow-peer-demo" \
  python3 tests/service_test.py build/release/matching_server \
  ServiceTest.test_slow_client_is_closed_while_healthy_client_keeps_completing -v
```

All seven rows completed an independent 130-command warmup and 130-command
workload, for 14 successful runs; their reference checks and independent summary
passed. These are functional smoke samples, not formal performance results.
The slow-peer case closed one slow connection while all 1,001 admitted commands
completed. Application send high-water was 8,174 bytes against an 8,192-byte
limit. Its explicit delivery-loss counters were retained; internal completion
does not mean that the disconnected client received every result.

## Earlier sanitizer development snapshot

The same VM previously tested a frozen **dirty** tree based on M1 commit
`b0293a36e4cff5a6ca4634c0df8af956f82ef2d3`. A 106-file SHA256 manifest, the
recorded Git status and successful guest-side hash verification identify this
snapshot; it is not commit `ce9e94f` or a clean-checkout result.

| Configuration | Toolchain | Passed/discovered | CTest elapsed |
|---|---|---:|---:|
| Debug | GNU 13.3.0 | 92/92 | 7.72 s |
| Release | GNU 13.3.0 | 93/93 | 7.85 s |
| ASan + UBSan | GNU 13.3.0 | 92/92 | 187.84 s |
| TSan | Clang 18.1.3 | 92/92 | 9.23 s |

Every configuration used a separate preset directory and executed the real
service, CLI and loadgen tests. All 27 project translation units had the
expected sanitizer flags in the two sanitizer builds. No sanitizer/race
diagnostic or skipped test was reported. The exact configure/build/test harness
is archived as `run-dev-validation.sh`; it reused dependency sources from the
existing TSan build. Only the later clean reproduction proves fresh dependency
download. The dirty snapshot predates the new ServerLifecycle regression and
does not establish sanitizer coverage for later source changes.

## Separate Linux identity/restart follow-up

On 2026-10-17, two follow-up cases ran against the existing Release server from
clean guest commit `85de7f3262bc96a8ff889226592282cee1c57684`. The updated Python
test and its two existing helpers were copied to ignored `build/followup/`;
tracked guest source was unchanged and no build was run for this follow-up.
The test files and server binary have their own recorded SHA256 values, so this
does not relabel the earlier 94-test suite or claim that the newer tests were
already committed in `85de7f3`.

```sh
LLMATCH_SERVICE_ARTIFACTS="$PWD/build/followup/identity-restart/artifacts" \
  python3 build/followup/identity-restart/service_test.py build/release/matching_server \
  ServiceTest.test_disconnect_retains_orders_and_reconnect_gets_new_identity \
  ServiceTest.test_process_restart_starts_empty_and_cannot_cancel_previous_orders -v
```

Both passed. Linux `/proc` observations recorded old FD 9 and new FD 9, while
ClientId changed from 1 to 2; ownership and retained-order behavior remained
correct. A restarted process returned an empty book and could not cancel the
old process's order. Before/after Git status remained empty. The server SHA256
was `2348899014ba8415c1b4f6212541fb9ef61c6c5644af8631ae1a56a2812c4c23`.

## Evidence inventory and limits

Paths below are repository-relative local inventories, currently under ignored
`build/`; they are not public download URLs. Final delivery must preserve these
materials in the permanent M2 archive and link that archive from the release.

| Evidence root | Files answering the acceptance question |
|---|---|
| `build/m2-vm/evidence/clean-ce9e94f/` | `summary.json`, `commands.json`, `environment.json`, `remote.txt`, `commit.txt`, initial/final status, `first-configure.log`, `CMakeCache.txt`, `compile_commands.json`, `binaries-sha256.txt`, `SHA256SUMS` |
| Same root, tests | `build.log`, `ctest.log`, `discovery.json`, `results.xml`, `groups-execution.json`, `Testing/`, `service-artifacts/`, `loadgen-test-evidence/`, `service-benchmark-evidence/`, `replays/` |
| Same root, demonstrations | `t10-two-clients.py`, `two-client-demo/`, `network-smoke/`, `independent-smoke-summary.log`, `slow-peer-demo/` and their top-level logs |
| `build/m2-vm/evidence/dirty-validation-20261016T230725Z/` | Source manifest/hash verification, environment, exact validation harness, each preset's logs/discovery/JUnit/compile commands and raw artifacts |
| `build/m2-vm/evidence/followup-identity-restart-85de7f3/` | `test.log`, `commit.txt`, before/after status, `source-binary-sha256.txt`, copied test source and `artifacts/disconnect-retained-wcywg6uk/fd-reuse.json`; both restart process records |

These records establish only their stated revisions and checks. They do not
replace the latest PR checks, exact merged-main push CI, the formal Linux
measurement matrix, profiling or the final release/archive. The separate
[120,000-command service validation](m2_long_validation.md) also has its own
platform and source scope.
