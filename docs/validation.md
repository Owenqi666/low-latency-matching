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

The initial integrated core run passed 36/36 tests in Debug and ASan/UBSan.
Subsequent additions test reused output buffers, direct counter preservation,
reverse multi-price sweeps and trace parsing; their final totals will be recorded
after execution. Logs and JUnit results are under `build/evidence/` locally.

The manual fixture oracle was negatively checked: its first expected maker price
was temporarily changed from 100 to 99. Both engine fixture tests failed and
CTest returned 8. Restoring the expectation made the 36-test suite pass again.
See `build/evidence/fixture-price-mutation.log` and `core-debug.log` locally.
This mutation changed only the test expectation, not either engine.

For real remote CI and intentional failure/recovery runs, see
[ci_evidence.md](ci_evidence.md). Random differential, shrinking and long-run
evidence will be added once executed.
