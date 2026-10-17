# M4 storage allocation diagnosis

## Historical macOS baseline diagnosis

The following entry records the pre-candidate diagnosis. Its original scope
and future-work statement are retained; the completed Linux A/B comparison
appears below.

This is a short, instrumented macOS diagnosis, not Linux formal performance or
an uninstrumented startup benchmark. The list OrderBook and MatchingEngine
sources equal the accepted M3 sources. Development HEAD was `6b92335`; new
diagnostic/generator files were uncommitted and are bound by individual hashes
in `build/m4-storage-diagnostic/provenance.json`.

Apple Clang 21.0.0 compiled the standalone probe with C++20, `-O3 -DNDEBUG`
on macOS 26.6.2 arm64. The executable's new/delete replacements are linked only
into this diagnostic. Construction, setup, measured limit/market/cancel and
destruction are counted separately. Parsing, Reference, event sinks, snapshots,
invariant checks, formatting and direct libc allocation are excluded. Requested
bytes exclude allocator metadata and the diagnostic allocation header.

Each trace has C=1,000 and 2,000 input commands after setup. Every command's
ordered events and full snapshot match the independent Reference. All tracked
engine blocks/bytes return to zero after destruction.

| Scene | Active orders during input | Resting additions | Allocation requests in limit calls | Cancel frees | Market frees |
|---|---:|---:|---:|---:|---:|
| mixed | 500–501 | 667 | 2,001 | 1,998 | 0 |
| cancel_heavy | 499–500 | 976 | 1,969 | 1,970 | 0 |
| near_full_reuse | 999–1,000 | 971 | 1,942 | 1,828 | 114 |

The near-full input has 58 CapacityExceeded rejections, 914 successful cancels
and 57 fully filled maker orders. Its stable price levels make each successful
resting addition allocate a list node and an OrderId hash node. That observation
supports testing the slot hypothesis; it does not identify the service's dominant
cost or imply that slots eliminate hash/map allocation. Mixed adds/removes price
levels as well, explaining its different request population.

On this libc++ build, empty engine requested heap bytes are 10,888, and a full
1,000-order setup uses 116,040 requested bytes. These are not process RSS or
Linux allocator measurements. The probe saves current/high-water RSS separately
and retains all 100 fresh OrderBook constructor observations. Those constructor
times still include the replacement allocator's header/alignment overhead and
cannot establish a production speedup.

The probe contract test passed. It checks full-book rejection, partial versus
complete fill, owner/OrderId reuse, exclusion of Reference/snapshot allocations,
allocation/free lifetime balance and preservation of existing output. Root
verification independently matched all 16 recorded artifact SHA-256 values and
the three production source files against M3. See `root-verification.json` and
`root-probe-test.log` in the same evidence directory. The source/probe/input hashes,
commands, full counts and original observations will be included in the M4
permanent archive; these local paths alone are not a public archive.

The outcome permits one bounded slot candidate under the already frozen plan.
Both frozen Linux builds will run the same diagnostic separately from formal
timing, so cross-platform allocation sizes are not used as an A/B comparison.

## Frozen Linux A/B diagnosis

Six sequential short probes compared list control
`97fdc6ee165201b0ab9b3997879f5296fb508d9f` with slot candidate
`4cf669ff2e932c6f27adeca0a9e143ffd03430b1` on the Ubuntu 24.04 arm64 guest,
Linux `6.8.0-147-generic`. Only the two OrderBook source files differ. Both
use the same probe and generator source hashes, compiler settings, inputs,
C=1,000 and 2,000 input commands after setup. The order was mixed A/B,
cancel-heavy A/B, then near-full-reuse A/B. This work ran separately from
the uninstrumented formal core matrix.

The host checked all 103 copied files, the six source/binary/input bindings,
Reference outcomes, declared workload counts and complete allocation/free
balances. All six runs match the independent Reference; all tracked blocks
and requested bytes return to zero after engine destruction. The inspection
receipt is `build/m4-storage-diagnostic/linux-host-verification.json`.
The original six probes, per-operation details, all 100 constructor observations
per run, commands, identities and environment are under
`build/m4-storage-diagnostic/linux`, with the aggregation in `comparison.json`.
These local paths will need the final permanent archive; they do not establish
that M4 has already been published.

### Allocation requests and reclamation

Counts and bytes below cover only the 2,000 input commands. Setup,
constructor and destruction are recorded in separate phases. The counter
intercepts global C++ new/delete only while the engine runs. It includes
price-map nodes, OrderId hash nodes/buckets and order storage; it excludes
parsing, Reference, sinks, snapshots, invariant scans, formatting and direct
libc allocations. Requested bytes exclude allocator metadata, padding and
the diagnostic replacement allocator's 24-byte header.

| Scene | Resting additions | Allocations A / B | Frees A / B | Requested allocation bytes A / B |
| --- | ---: | ---: | ---: | ---: |
| mixed | 667 | 2,001 / 1,334 | 1,998 / 1,332 | 112,056 / 69,368 |
| cancel_heavy | 976 | 1,969 / 993 | 1,970 / 994 | 94,920 / 40,128 |
| near_full_reuse | 971 | 1,942 / 971 | 1,942 / 971 | 93,216 / 38,840 |

B removes exactly one allocation request per successful resting addition in
these probes. In near-full-reuse, cancellations free 1,828 blocks for A and
914 for B; 57 markets fully consume one maker each and free 114 versus 57
blocks. The same trace has 58 CapacityExceeded limits and never drops below
999 live orders. B still allocates the OrderId hash node on every resting
addition. Mixed/other paths can also allocate price levels, so this is not
evidence for a zero-allocation engine or service. Changed price-level payload
sizes also affect requested-byte totals; differences cannot all be labeled
slot-only memory reductions.

### Reserved and live memory

The candidate's slot is 56 bytes, aligned to eight bytes. At C=1,000 the
fixed slot array therefore occupies 56,000 requested bytes. Construction
makes one tracked request totaling 11,048 bytes for A, and two totaling
67,048 bytes for B. The unchanged hash-bucket reservation remains part of
both. `sizeof(OrderBook)` changes from 152 to 184 bytes; `sizeof(MatchingEngine)`
from 296 to 328, while `sizeof(Order)` stays 40. These object sizes are separate
from the tracked requested heap bytes.

| Observation | Live orders | A requested live heap bytes | B requested live heap bytes |
| --- | ---: | ---: | ---: |
| Empty, all three scenes | 0 | 11,048 | 67,048 |
| Mixed after setup | 500 | 60,200 | 88,072 |
| Cancel-heavy after setup | 500 | 61,352 | 89,096 |
| Near-full-reuse after setup and at end | 1,000 | 108,200 | 108,072 |

Preallocation raises empty and half-full memory requirements. The 128-byte
requested-memory difference at full capacity does not erase that cost or
prove a general memory reduction. In the near-full probe, whole-process
current RSS after setup is 4,460,544 bytes for A and 4,329,472 for B;
reported high-water RSS is 19,570,688 for both. Those observations include
inputs, Reference, snapshots and the diagnostic process, and reflect a
different measurement from live requested engine bytes. Neither current nor
high-water RSS isolates the slot array; RSS changes cannot be equated with
allocator request savings.

### Instrumented constructor observations

Each run records 100 fresh OrderBook constructions, destroys the object
outside the interval and excludes input parsing and Reference. Allocation
counters are disabled in this timing loop, but the diagnostic allocator's
header/alignment machinery remains linked. The interval includes bucket
reservation and, for B, the fixed slots. It does not isolate slot-only cost
and is not an uninstrumented production startup measurement.

| Scene | A median ns [min, max] | B median ns [min, max] | First construction ns A / B |
| --- | ---: | ---: | ---: |
| mixed | 83.5 [83, 749] | 916 [874, 1,625] | 749 / 1,625 |
| cancel_heavy | 84 [83, 584] | 916.5 [834, 1,583] | 584 / 1,583 |
| near_full_reuse | 83 [83, 625] | 958 [916, 1,833] | 625 / 1,833 |

All observations are retained without subtracting a clock constant. The
longer instrumented candidate constructors disclose an initialization cost;
their absolute values or ratios must not be presented as production startup
latency. The Linux allocation counts and the [formal core report](m4_report.md)
answer different questions. Fewer allocations alone neither locates the
service bottleneck nor satisfies the frozen throughput and service rules.
