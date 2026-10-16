# Correctness evidence

This document records executed checks, not a proof over all possible inputs.
The exact build/commit and final totals are updated at milestone acceptance.

## Core implementation checks

Both engines passed the same hand-calculated event/snapshot fixture. Tests cover
maker pricing, FIFO after partial fills and middle cancellations, both sides,
market IOC, conservative full-book admission, duplicate/owner rejection,
request/ID reuse, self-trading, numeric limits and call-level output/sequence
errors. The independent reference chooses by price and arrival sequence even
after swap deletion changes vector order.

The integrated core/trace suite passed 48/48 tests in Debug, Release and
ASan/UBSan. Reused output buffers, direct counter preservation, reverse
multi-price sweeps and strict trace parsing are included. The next integrated
replay/differential suite passed 58/58 in Debug and ASan/UBSan, then the CLI
contract test passed separately. The PR run below validates all 59 together.
Logs and JUnit results are under `build/evidence/` locally.

The manual fixture oracle was negatively checked: its first expected maker price
was temporarily changed from 100 to 99. Both engine fixture tests failed and
CTest returned 8. Restoring the expectation made the 36-test suite pass again.
See `build/evidence/fixture-price-mutation.log` and `core-debug.log` locally.
This mutation changed only the test expectation, not either engine.

At code commit `5ddea0546fda93c986b6c2cde1c387cb176a96a7`, a fresh Release build
ran `LLMATCH_LONG_DIFFERENTIAL=1` with the fixed-seed test filter and passed
100 seeds × 10,000 commands = 1,000,000 comparisons. The XML explicitly records
the seed/command counts and capacities. Evidence: `build/evidence/t06-long-current.xml`.
This rerun binds the long check to the committed tool implementation.

The same PR head passed all three Ubuntu 24.04 jobs in
[PR CI run 38970459769](https://github.com/Owenqi666/low-latency-matching/actions/runs/38970459769).
PR jobs check the merge revision; the job records its actual checkout SHA.
Final delivery still requires the final PR head and merged main to pass.

For intentional CI failure/recovery runs see [ci_evidence.md](ci_evidence.md).
For generator, local mutation and reduction evidence see [t06_evidence.md](t06_evidence.md).
The reduced maker-price case is permanently registered as `regression_maker_price`.
