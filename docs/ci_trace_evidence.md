# T07 remote failure-trace artifact probe

Recorded on 2026-10-16. This is an isolated failure/recovery experiment on
`ci/trace-artifact-probe`, cloned from feature revision
`5ddea0546fda93c986b6c2cde1c387cb176a96a7`. The probe branch was not merged.
It does not establish CI status for later feature or main revisions.

## Actual remote failure

The only injected source change was in `src/matching_engine.cpp`:

```cpp
trade.price = maker.price + 1; // Intentional T07 CI failure-artifact probe
```

The original assignment was `trade.price = maker.price;`. The mutation was
committed only in a separate temporary clone, not in the development checkout.

| Stage | Commit | GitHub Actions run | Observed result |
| --- | --- | --- | --- |
| Intentional wrong-price mutation | `9f887dde5d0280a866e9024adfc9210e8b19b7c9` | [38970552877](https://github.com/Owenqi666/low-latency-matching/actions/runs/38970552877) | All three jobs configured and built; CTest exited 8 in Debug, Release and ASan/UBSan; all three artifact uploads succeeded. |
| Original price assignment restored | `f759395a9ca39c896da4e5668949fd56d5ef6ef7` | [38970740907](https://github.com/Owenqi666/low-latency-matching/actions/runs/38970740907) | Debug, Release and ASan/UBSan each passed all 59 CTest cases; all uploads succeeded. Exact SHA and counts were checked in downloaded logs. |

The workflow was manually dispatched for each branch revision:

```sh
gh workflow run ci.yml --ref ci/trace-artifact-probe \
  --repo Owenqi666/low-latency-matching
```

The failed run executed 59 CTest cases per configuration. Debug and Release had
11 intentional failures. ASan/UBSan had 12: besides event mismatches, the
injected `+1` overflowed `INT64_MAX` in `ConfigAndQuantityExtremes`, and UBSan
reported it and failed that test. This diagnostic belongs to the injected defect,
not to the restored engine.

Downloaded toolchain logs identify GNU C++ 13.3.0
(`Ubuntu 13.3.0-6ubuntu2~24.04.1`), CMake 3.31.6 and Ninja 1.13.2 on the configured
Ubuntu 24.04 runners. `checkout-sha.log` in all three failure artifacts equals
the mutation commit above.

## Downloaded evidence and local reproduction

This download actually completed successfully:

```sh
gh run download 38970552877 --repo Owenqi666/low-latency-matching \
  --dir /private/tmp/low-latency-t07-trace-artifacts-20261016
```

All three artifacts named
`ci-evidence-<preset>-38970552877-1` contained
`<preset>/failures/seed-1295056896/` with:

- `config.txt`: capacity 1, max price 1000, max quantity 1000.
- `input.trace`: the actual 2,000-command generated input.
- `metadata.txt`: generator `mt19937_64-modulo-v1`, seed `1295056896`, command
  count 2000, input hash `fnv1a64:87a8ca89317f6aa2`, config hash
  `fnv1a64:c93eab11afc3a2e5`.
- `difference.txt`: first difference at command 2, event index 1,
  `event_value_kind_2` (Trade), with both process results, complete event
  sequences and both canonical snapshots.

The two leading commands buy-rest 8 at 589, then sell-market 1000. Both engines
fill 8 and IOC-cancel 992; the mutant incorrectly reports trade price 590 while
the reference reports 589. Both final books are empty. Full event comparison
therefore detects a defect that final-state-only comparison would miss.

The downloaded files have identical contents across the three presets:

| File | SHA-256 (each downloaded copy) |
| --- | --- |
| `config.txt` | `9dab92d264d4b701747cf537e99084d086482119bde9996b10f3ca3fcc7cf63a` |
| `input.trace` | `f346a6db2725adddce25404bfbb7e946cfaf45b80f31390f3e50bee727cf7d98` |
| `metadata.txt` | `51bef3d5cdf997bf0f17d5f7892bc7b6aabcb250d3c3bd934d6df1ec3c56104f` |
| `difference.txt` | `885c866521970118b9d21c9f41dd50e195f65ad467e6c4ec97a27f085644d1a9` |

Before restoring the source, a local mutant replay executable was built in the
isolated clone using:

```sh
clang++ -std=c++20 -O1 -g -Iinclude -Itools -Ireference \
  apps/replay_main.cpp tools/differential.cpp tools/trace_io.cpp \
  src/order_book.cpp src/matching_engine.cpp reference/reference_engine.cpp \
  -o build/t07-probe/replay_mutant
```

Each downloaded config/input pair was replayed with
`replay_mutant --engine compare --config <downloaded-config> --input <downloaded-trace> --output-dir <local-dir>`.
All three invocations exited 2 at command 2. Each locally generated
`difference.txt` was checked byte for byte against its downloaded report and
matched exactly. Local detailed command/exit/hash evidence is retained at
`/private/tmp/low-latency-t07-trace-probe-20261016/build/t07-probe/download-replay-evidence.json`.

## Restoration

Restoration copied the original production file from the feature revision,
committed and pushed it, then dispatched the workflow again. After restoration:

```sh
git diff 5ddea0546fda93c986b6c2cde1c387cb176a96a7 --exit-code
```

returned zero in the isolated clone: the restored tracked tree exactly matches
the base feature tree. The probe's wrong-price commit is not part of the
feature branch. Recovery workflow [38970740907](https://github.com/Owenqi666/low-latency-matching/actions/runs/38970740907)
completed successfully in all three configurations. Its artifacts were also
actually downloaded with `gh run download`; every `checkout-sha.log` names
`f759395a9ca39c896da4e5668949fd56d5ef6ef7` and every `ctest.log` states
`100% tests passed, 0 tests failed out of 59`.

| Restored preset | Downloaded `ctest.log` SHA-256 |
| --- | --- |
| Debug | `5e180af724d2b69fbbc5dcaafa3e0784d73abbc43320b0f67f83d2c5292753fc` |
| Release | `12d44397e53a1a435115ca5c23cee6b8eb9c39a958a732e316aefb9a98b215b0` |
| ASan/UBSan | `dd14ef0d4a46ba4ae4a5ed6ea1121a2962fe965225e1e8982f38014d47734852` |

The restored replay executable was rebuilt from restored source using the same
Clang command with output `build/t07-probe/replay_restored`. Each of the three
downloaded 2,000-command traces then passed comparison with exit 0. Command and
exit details are retained in the temporary clone at
`build/t07-probe/restored-replay-evidence.json`; downloaded recovery log checks
are in `build/t07-probe/recovery-download-evidence.json`.

Thus this probe verifies failure detection, nonzero CI exit, actual artifact
upload and download, exact reproduction, restoration, and successful CI recovery.
Final feature/main CI and later benchmark-smoke coverage remain separate checks.

GitHub artifact retention is finite (14 days for these jobs). Successful
retrieval, file hashes and reproduction results are recorded here independently
of future artifact expiry.
