# M1 core benchmark method

The benchmark measures a synchronous, single-thread, in-memory matching core.
It has no network arrival process, input queue, service RTT or concurrency claim.
Results must identify the exact code revision, build, machine and input bytes.
Formal runs use Release without sanitizers; the executable rejects Debug and
detectable sanitizer builds. Correctness tests and sanitizer runs precede formal
measurement. Benchmark smoke checks prove operation and artifact completeness,
not a latency target.

## Reproduction and state

Build with the release preset, generate workload manifests, then use the Python
runner to save environment and input identities. The core binary also runs alone:

    build/release/bench_core --config CONFIG --setup SETUP.trace \
      --input INPUT.trace --repeats 5 --output-dir build/results/CASE
    build/release/clock_probe --output build/results/clock.json

Both setup and measured input use the versioned text format documented in
trace_format.md. The input must contain at least one command. Repeats default
to five; a shorter explicit count is useful for CI smoke checks and must not be
presented as the five-round acceptance result. Large workloads and raw outputs
belong outside version control; retain their manifest, hashes and result index.

Before any timed round:

1. Parse config, setup and input completely. Construct an independent production
   engine and vector reference model.
2. Execute the same setup and input in both engines, comparing the complete
   ordered event prefix after every command. Compare canonical snapshots after
   setup and after the measured input, and check final invariants. This benchmark
   verification intentionally does not sort and compare a full snapshot after
   every command; the dedicated differential tests perform that stronger check.
3. Derive workload characteristics from verified events using a separate active
   order ledger. Save the verified final snapshot, event/result totals and one
   verification CSV row for every input command.
4. Preallocate the result sink and latency sample array. Warm up a separate
   production engine using the identical setup and input and verify its results.
5. For each mode in each round, construct another new engine and execute the
   identical setup outside timing. Never reuse the consumed warmup book or copy
   an engine's internal iterators.

Setup commands contribute to engine sequences and initial state but are excluded
from reported command counts, event counts and measured durations. Each round's
input events therefore have exactly the same deterministic sequence values.

## Two timing modes

Latency times one process call with steady_clock immediately before and after
the call. The result status check, event consumption, metadata extraction and
sample recording happen after the second clock read. Each sample includes core
matching and output generation, plus the unavoidable clock boundary effects.
It excludes parsing, RNG, setup, full-book checks, reference work and file I/O.
Per-command timing changes execution rhythm and cache state; its results cannot
be used as the separately measured batch throughput.

Throughput times the entire input loop. Every iteration processes one command,
checks process status, counts output event/result kinds and feeds every field of
every valid output event into a rolling integer checksum. This keeps each result
observable. Those checks, counts and checksum operations are harness cost inside
the throughput interval. They are disclosed rather than subtracted or hidden.
No per-command clock read occurs in throughput mode.

After either mode, outside its timing interval, the benchmark compares completed,
accepted, rejected, trade and event totals, plus the full-event rolling checksum,
with the verified replay. It checks invariants and compares the exact final
snapshot. Any mismatch exits nonzero and prevents a successful summary.
Full event equality was already checked between the two engines before timing;
the checksum is an additional measured-run consistency check, not a proof of
collision-free equality. All exceptions stop the run.

Five rounds are retained, including slower rounds. Each round runs latency then
throughput from a fresh engine. No round is selected because it is fastest.
Keep background activity and power conditions consistent and report conditions
that cannot be controlled. The benchmark does not pin threads or change CPU
frequency. That limitation belongs in the environment manifest.

## Files and metrics

summary.json uses schema_version 1. config_hash, setup_hash and input_hash
are raw-byte FNV-1a64 strings as specified by trace_format.md. The Python runner
additionally records SHA-256. Raw hashes include comments and line endings.
The binary checks the hashes before parsing and after all rounds; a change
fails the run rather than attributing timings to different input bytes.
summary.json is written only after all rounds succeed; a previous summary in
the output directory is removed at the start of a valid invocation.

The verification object contains counts, checksum, final_snapshot_hash,
setup_live_orders, end_live_orders and observed live-order, event, trade and
swept-level distributions. verification.csv has these columns:

    index,command_kind,result,reject_reason,event_count,trade_count,swept_levels,live_orders

index starts at zero. command_kind and reject_reason use contract enum integers.
result is CompletionStatus (Accepted=1, Rejected=2). live_orders is the number
after processing that command. swept_levels counts distinct maker prices touched
by its Trade events; prices progress monotonically during a single command.
These metrics describe the actual generated stream, including rejected requests,
and are all computed outside measurement. Split successful/failed cancels,
command kinds and accepted/rejected results rather than hiding rejection paths
inside an overall average. The ledger records all observations, not samples.

Each latency CSV contains exactly one row per measured input command:

    index,command_kind,result,reject_reason,event_count,trade_count,ns

Round records contain mode, round, verified, final_snapshot_hash, all counts and
checksum, elapsed_ns, batch_elapsed_ns, p50_ns, p99_ns, p99_sample_threshold_met, samples_file,
max_rss_bytes, cpu_user_us and cpu_system_us.

- Latency elapsed_ns is the sum of individual process samples.
  batch_elapsed_ns is the complete loop duration including clocks, event
  consumption and recording. Use CSV samples for latency distributions.
- Throughput elapsed_ns equals batch_elapsed_ns. Divide completed, accepted and
  trades by this duration to report completed commands/s, accepted commands/s and
  trades/s. Report rejected/completed alongside those rates. Quantile and sample
  file fields are null in throughput mode.
- p50 and p99 use nearest-rank: sorted sample at ceil(p*N), with one-based ranks.
  Fewer than 100000 samples sets p99_sample_threshold_met=false; the percentile
  remains visible but must be labeled below the reporting sample threshold.
  Meeting that count threshold does not establish statistical stability or
  confidence. No p99.9 is emitted.
- The sink uses C+4 Event slots; sink_capacity, sink_bytes and event_bytes record
  this memory cost. Map/list nodes still allocate inside process.
- CPU fields are process user/system getrusage deltas around the complete mode
  loop. Peak RSS is the process high-water mark at that point, including parsed
  inputs, verification, warmup and earlier rounds. It is not isolated core heap
  usage. macOS ru_maxrss is already bytes; Linux KiB is multiplied by 1024.

verified_final.snapshot and every latency_N.snapshot / throughput_N.snapshot
use the same canonical format and must match exactly. Formal reports bind these
artifacts, workload generation parameters, build environment and commit together.
Another machine should reproduce the semantics and artifacts; it need not
reproduce identical timing values.

## Clock probe

clock_probe preallocates storage, warms the clock, and measures 100000 back-to-back
clock pairs. It records the nominal clock period, smallest observed positive
interval, zero intervals and nearest-rank p50/p99. A batch duration covers two
clock reads plus duration recording per sample. A separate batch records one
timestamp per sample and reports its clock-plus-store overhead. The vectors are
consumed outside timing to keep stores observable.

Nominal period is a representation property; the smallest observed positive
interval is an empirical observation, not guaranteed hardware resolution.
Neither experiment perfectly isolates process-call timing overhead, and neither
constant is subtracted from matching samples. Very short measured calls may be
dominated by clock granularity; the batch throughput mode supplies a separate,
lower-clock-frequency view.
## Paired M4 order-storage comparison

M4 compares list control `97fdc6ee165201b0ab9b3997879f5296fb508d9f` with
fixed-slot candidate `4cf669ff2e932c6f27adeca0a9e143ffd03430b1`. Both retain
the same shared tools and input generators. The final list decision does not
remove the candidate from its fixed Git revision or release source archive.

For independent Linux builds, use new source/dependency/build directories:

```sh
git clone https://github.com/Owenqi666/low-latency-matching.git /tmp/llmatch-m4-control
git -C /tmp/llmatch-m4-control checkout --detach 97fdc6ee165201b0ab9b3997879f5296fb508d9f
git clone https://github.com/Owenqi666/low-latency-matching.git /tmp/llmatch-m4-candidate
git -C /tmp/llmatch-m4-candidate checkout --detach 4cf669ff2e932c6f27adeca0a9e143ffd03430b1
for m4_source in /tmp/llmatch-m4-control /tmp/llmatch-m4-candidate; do
  (
    cd "$m4_source"
    cmake --preset release -DCMAKE_CXX_COMPILER=g++
    cmake --build --preset release --parallel 2
    ctest --preset release --output-on-failure --no-tests=error
  )
done
```

With both builds complete and no concurrent build/test/profiler activity, run
the frozen five-scene core matrix from the candidate checkout:

```sh
cd /tmp/llmatch-m4-candidate
python3 scripts/run_core_pair.py \
  --baseline-binary /tmp/llmatch-m4-control/build/release/bench_core \
  --baseline-source /tmp/llmatch-m4-control \
  --candidate-binary /tmp/llmatch-m4-candidate/build/release/bench_core \
  --candidate-source /tmp/llmatch-m4-candidate \
  --manifest data/workloads/m4-core-formal.json --output-dir /tmp/m4-core-pair
python3 /tmp/m4-core-pair/tool-evidence/summarize_core_pair.py /tmp/m4-core-pair
```

Capture the actual host/VM configuration separately and pass its JSON with
`--host-environment FILE` when available. The runner captures guest/build/tool
identities; a host record must describe actual conditions, not a template.
Always choose a new output directory and preserve failed batches.

The enclosing matrix checks five adjacent AB/BA pairs for each of mixed,
cancel_heavy, sweep, clustered and near_full_reuse: 25 pairs, 100 separate
latency/throughput intervals at C=1,000 with 100,000 input commands. Every
invocation has Reference verification and warmup. A constituent repeats=1
report alone is not a five-pair formal result. For a short functional replay,
add `--commands 2000 --rounds 2 --scenario near_full_reuse`; the resulting
smoke label cannot support or revise the formal adoption decision.

See the [M4 report](m4_report.md), [frozen plan](m4_experiment_plan.md) and
[evidence index](m4_evidence_index.md) for all pairs, allocation/startup costs,
short timing windows, clock quantization and shared-VM limitations.
