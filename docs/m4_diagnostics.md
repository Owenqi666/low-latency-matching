# M4 baseline allocation diagnosis

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
