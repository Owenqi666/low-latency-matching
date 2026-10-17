# M5 reproduction

These commands reproduce the offline ITCH path and its existing-service
regressions. They are instructions, not a claim that CI, publication or this
reproduction has completed. See [supported semantics](itch_scope.md),
[the independent-module decision](adr/007-independent-itch-reconstruction.md)
and [the frozen plan](m5_plan.md) for scope and measurement settings.

## Fresh Linux checkout

Use Linux with Git, a C++20 GCC toolchain, CMake >= 3.24, Ninja and Python >= 3.10.
The first dependency download needs network access. An existing Linux VM and
system toolchain can be reused; no VM copy is needed.

Start from a clean public checkout of the exact revision to reproduce. Its
commit must be fetchable from the public repository. Choose a new base directory;
the helper refuses to overwrite an existing checkout or evidence directory.
Locate the saved authoritative historical prefix and its original capture
receipt first; replace the two example paths below with those existing files.
The historical-input section describes acquisition only if no such input exists.

```sh
set -euo pipefail
M5_SHA="$(git rev-parse HEAD)"
M5_BASE="$PWD/build/m5-reproduction"
M5_REAL_INPUT='/absolute/path/to/private-history/prefix.bin'
M5_CAPTURE='/absolute/path/to/private-history/capture.json'
mkdir -p "$M5_BASE"
git status --porcelain > "$M5_BASE/bootstrap-status.txt"
git rev-parse HEAD > "$M5_BASE/bootstrap-sha.txt"
sha256sum scripts/reproduce_m5.py > "$M5_BASE/bootstrap-script.sha256"
python3 scripts/reproduce_m5.py --sha "$M5_SHA" \
  --checkout "$M5_BASE/source" --evidence "$M5_BASE/t06" \
  --real-input "$M5_REAL_INPUT" --capture "$M5_CAPTURE"
```

The helper clones the public repository, detaches at that SHA, downloads fresh
CMake dependencies and builds Release with GCC. Do not supply
`FETCHCONTENT_SOURCE_DIR_*` overrides or an old build/cache. It records the
actual checkout, environment, compiler, cache, compile commands and binary
hashes in `t06/`. Existing dependency source overrides are not a fresh install.

It then checks dynamic discovery and JUnit for all nine Release groups, runs
all discovered tests, demonstrates two real `matching_client` processes,
verifies golden ITCH bytes, demonstrates a truncated-input failure, and runs
core, seven-scenario network and small ITCH smoke checks with summaries.
It also checks the saved historical input against the capture identity and
independently replays it with the new checkout's tools into `t06/itch-real`.
`t06/run.json` records commands, exits and status. Test evidence also remains
under the new checkout's `build/release/`; retain it with the T06 evidence.
The helper records `acquisition_repeated=false`: the saved prefix is reused,
not downloaded again. Transfer that single authoritative input to an existing
VM if needed; do not duplicate the VM or reacquire the source for T06.

## Long correctness check and finite measurement

After T06 succeeds, use that same new checkout. The long run creates one input,
then streams C++ audit output against independent Python decoding of those bytes.
Its default frozen seed produces 150,000 messages, with the actual target-update
count recorded in `workload.json`; require at least 100,000 compared updates.

```sh
cd "$M5_BASE/source"
python3 scripts/create_itch_workloads.py --scenario long_verify --messages 150000 \
  --output-dir "$M5_BASE/long-input"
python3 scripts/verify_itch.py --binary build/release/itch_replay \
  --input "$M5_BASE/long-input/input.bin" --symbol TEST \
  --output-dir "$M5_BASE/long-verification"
```

The verifier retains counts, input/tool/binary identities, checkpoint coverage
and final-file checks in `verification.json`. It does not save every streamed
audit line. On failure, it preserves exact original bytes and a verifier replay
command with the original mode, capacity and checkpoint settings. Keep those
artifacts even when a later fix succeeds.

Run the formal matrix only after correctness passes, sequentially with no
concurrent build, compression or profiling. This command has no dimensions
overridden: it creates one authoritative input per scenario, each with
1,000,000 messages, verifies all three, then runs both modes with one independent
warmup and five measured intervals each (30 measurements and six warmups).

```sh
python3 scripts/run_itch_bench.py --binary build/release/bench_itch \
  --replay build/release/itch_replay --source "$PWD" \
  --output-dir "$M5_BASE/formal"
python3 scripts/summarize_itch_bench.py "$M5_BASE/formal"
```

The runner requires clean Linux source and an unsanitized Release build. Its
manifest binds source/build/tool/input identities, verification receipts and
every planned interval. `report.json` and `report.md` are derived from those raw
results. Adding `--messages`, `--rounds` or `--scenario` explicitly labels a run
as smoke; a short run does not replace the formal matrix. Report all rounds,
CPU/RSS and VM limitations; there is no minimum throughput or speedup gate.

After the matrix, make one separate resource observation of the already
verified real prefix. Keep its original capture identity with this result:

```sh
build/release/bench_itch --input "$M5_REAL_INPUT" --symbol AAPL --prefix \
  --mode rebuild --output "$M5_BASE/real-resource.json"
```

This single traversal is not another synthetic scenario or a whole-day benchmark.

## Bounded historical input

Historical bytes are not supplied by this repository. A new acquisition is an
explicit separate step; do not silently repeat it during every test or CI run.
The frozen source selection and cutoff can be acquired once as follows:

```sh
python3 scripts/capture_itch_prefix.py \
  --url 'https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/12302019.NASDAQ_ITCH50.gz' \
  --date 2019-12-30 --symbol AAPL --target-updates 1000 \
  --output-dir "$M5_BASE/private-history"
python3 scripts/verify_itch.py --binary build/release/itch_replay \
  --input "$M5_BASE/private-history/prefix.bin" --symbol AAPL --prefix \
  --output-dir "$M5_BASE/history-verification"
```

With `set -e` above, capture failure stops before verification. The capture is
limited to 1 GiB compressed bytes read and a 256 MiB retained uncompressed
continuous day-start prefix. It stops at a whole-message boundary after at
least 1,000 target updates including an add and a subsequent change. The receipt
records the actual URL, response identity, bytes consumed, cutoff, counts and
prefix SHA-256. Acquisition alone is not semantic verification.

Alternatively, reuse the saved authoritative `prefix.bin` and its capture
receipt, verify their recorded SHA-256, and run only the second command with
that path. State explicitly whether acquisition was newly executed or the
saved input was reused. Do not claim whole-day coverage, a full-file checksum
or a whole gzip CRC from a bounded upstream read; do not fabricate an end marker.
If a usable real lifecycle cannot be captured within the budget, report T04 as
incomplete rather than substitute synthetic data.

Keep historical raw bytes local while redistribution permission is unconfirmed.
Publish acquisition instructions, identities and permitted summaries; public
CI uses synthetic data only. Retain one authoritative input per workload,
required failures and durable evidence, not duplicate VM disks, dependency
caches or whole-workspace backups. Final delivery additionally requires the
revision-specific PR/main artifact checks and verified Release described in
the plan; running this document does not establish those later gates.
