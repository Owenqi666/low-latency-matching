# M1 core benchmark report

All listed raw inputs, samples, counts and final snapshots passed validation.
Latency includes synchronous result generation. Throughput uses separately timed batches. No network/queue latency is measured.
p99 is marked when below the 100,000-sample reporting threshold. Meeting this threshold does not establish statistical stability.

## cancel_heavy / capacity 1000

Cancel/replace within a working pool; every twentieth cycle adds an explicit UnknownOrder cancellation.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 500 → 499; rejection fraction: 2.4390%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 41 | 42 | — | — | — | 2439 |
| throughput | 1 | — | — | 13441763.6 | 13113918.9 | 0.0 | 2439 |
| latency | 2 | 41 | 42 | — | — | — | 2439 |
| throughput | 2 | — | — | 14019838.1 | 13677894.2 | 0.0 | 2439 |
| latency | 3 | 41 | 42 | — | — | — | 2439 |
| throughput | 3 | — | — | 13674512.4 | 13340991.1 | 0.0 | 2439 |
| latency | 4 | 41 | 42 | — | — | — | 2439 |
| throughput | 4 | — | — | 13785180.3 | 13448959.7 | 0.0 | 2439 |
| latency | 5 | 41 | 42 | — | — | — | 2439 |
| throughput | 5 | — | — | 13814858.5 | 13477914.1 | 0.0 | 2439 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 1 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 1 | cancel / rejected / unknown_order | 2439 | 0 | 42 (below sample threshold) |
| 2 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 2 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 2 | cancel / rejected / unknown_order | 2439 | 0 | 42 (below sample threshold) |
| 3 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 3 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 3 | cancel / rejected / unknown_order | 2439 | 0 | 42 (below sample threshold) |
| 4 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 4 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 4 | cancel / rejected / unknown_order | 2439 | 0 | 42 (below sample threshold) |
| 5 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 5 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 5 | cancel / rejected / unknown_order | 2439 | 0 | 42 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## cancel_heavy / capacity 10000

Cancel/replace within a working pool; every twentieth cycle adds an explicit UnknownOrder cancellation.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 5000 → 4999; rejection fraction: 2.4390%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 41 | 42 | — | — | — | 2439 |
| throughput | 1 | — | — | 13761232.4 | 13425596.0 | 0.0 | 2439 |
| latency | 2 | 41 | 42 | — | — | — | 2439 |
| throughput | 2 | — | — | 13755001.1 | 13419516.7 | 0.0 | 2439 |
| latency | 3 | 41 | 42 | — | — | — | 2439 |
| throughput | 3 | — | — | 13961036.4 | 13620526.7 | 0.0 | 2439 |
| latency | 4 | 41 | 42 | — | — | — | 2439 |
| throughput | 4 | — | — | 13836123.3 | 13498660.2 | 0.0 | 2439 |
| latency | 5 | 41 | 42 | — | — | — | 2439 |
| throughput | 5 | — | — | 13828628.7 | 13491348.5 | 0.0 | 2439 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 1 | cancel / accepted / none | 48781 | 42 | 42 (below sample threshold) |
| 1 | cancel / rejected / unknown_order | 2439 | 0 | 125 (below sample threshold) |
| 2 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 2 | cancel / accepted / none | 48781 | 41 | 42 (below sample threshold) |
| 2 | cancel / rejected / unknown_order | 2439 | 0 | 208 (below sample threshold) |
| 3 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 3 | cancel / accepted / none | 48781 | 42 | 42 (below sample threshold) |
| 3 | cancel / rejected / unknown_order | 2439 | 0 | 83 (below sample threshold) |
| 4 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 4 | cancel / accepted / none | 48781 | 42 | 42 (below sample threshold) |
| 4 | cancel / rejected / unknown_order | 2439 | 0 | 125 (below sample threshold) |
| 5 | limit / accepted / none | 48780 | 41 | 42 (below sample threshold) |
| 5 | cancel / accepted / none | 48781 | 42 | 42 (below sample threshold) |
| 5 | cancel / rejected / unknown_order | 2439 | 0 | 125 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## clustered / capacity 1000

Insert an ask ladder, buy-market half its orders, then cancel the remainder. These are synchronous phases, not network bursts.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 500 → 507; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 42 | 666 | — | — | — | 0 |
| throughput | 1 | — | — | 11205685.9 | 11205685.9 | 3696979.9 | 0 |
| latency | 2 | 42 | 666 | — | — | — | 0 |
| throughput | 2 | — | — | 11159417.8 | 11159417.8 | 3681715.1 | 0 |
| latency | 3 | 42 | 667 | — | — | — | 0 |
| throughput | 3 | — | — | 11383416.3 | 11383416.3 | 3755616.7 | 0 |
| latency | 4 | 42 | 666 | — | — | — | 0 |
| throughput | 4 | — | — | 11125172.1 | 11125172.1 | 3670416.8 | 0 |
| latency | 5 | 42 | 667 | — | — | — | 0 |
| throughput | 5 | — | — | 11225076.8 | 11225076.8 | 3703377.3 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 1 | market / accepted / none | 1031 | 709 | 1041 (below sample threshold) |
| 1 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |
| 2 | limit / accepted / none | 65984 | 42 | 83 (below sample threshold) |
| 2 | market / accepted / none | 1031 | 708 | 1042 (below sample threshold) |
| 2 | cancel / accepted / none | 32985 | 42 | 42 (below sample threshold) |
| 3 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 3 | market / accepted / none | 1031 | 750 | 917 (below sample threshold) |
| 3 | cancel / accepted / none | 32985 | 42 | 42 (below sample threshold) |
| 4 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 4 | market / accepted / none | 1031 | 708 | 958 (below sample threshold) |
| 4 | cancel / accepted / none | 32985 | 42 | 42 (below sample threshold) |
| 5 | limit / accepted / none | 65984 | 42 | 42 (below sample threshold) |
| 5 | market / accepted / none | 1031 | 709 | 959 (below sample threshold) |
| 5 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## clustered / capacity 10000

Insert an ask ladder, buy-market half its orders, then cancel the remainder. These are synchronous phases, not network bursts.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 5000 → 5007; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 42 | 667 | — | — | — | 0 |
| throughput | 1 | — | — | 11190636.7 | 11190636.7 | 3692014.9 | 0 |
| latency | 2 | 42 | 667 | — | — | — | 0 |
| throughput | 2 | — | — | 11330107.0 | 11330107.0 | 3738028.9 | 0 |
| latency | 3 | 42 | 666 | — | — | — | 0 |
| throughput | 3 | — | — | 11357130.5 | 11357130.5 | 3746944.5 | 0 |
| latency | 4 | 41 | 667 | — | — | — | 0 |
| throughput | 4 | — | — | 11188445.6 | 11188445.6 | 3691292.0 | 0 |
| latency | 5 | 42 | 708 | — | — | — | 0 |
| throughput | 5 | — | — | 11197790.7 | 11197790.7 | 3694375.1 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 1 | market / accepted / none | 1031 | 750 | 1041 (below sample threshold) |
| 1 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |
| 2 | limit / accepted / none | 65984 | 42 | 42 (below sample threshold) |
| 2 | market / accepted / none | 1031 | 750 | 1000 (below sample threshold) |
| 2 | cancel / accepted / none | 32985 | 42 | 42 (below sample threshold) |
| 3 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 3 | market / accepted / none | 1031 | 709 | 917 (below sample threshold) |
| 3 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |
| 4 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 4 | market / accepted / none | 1031 | 750 | 1042 (below sample threshold) |
| 4 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |
| 5 | limit / accepted / none | 65984 | 41 | 42 (below sample threshold) |
| 5 | market / accepted / none | 1031 | 750 | 958 (below sample threshold) |
| 5 | cancel / accepted / none | 32985 | 41 | 42 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## mixed / capacity 1000

One working order at a time: sell10, buy limit3, buy market2, cancel5, then bid7/cancel.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 500 → 500; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 41 | 42 | — | — | — | 0 |
| throughput | 1 | — | — | 12828805.5 | 12828805.5 | 4276354.0 | 0 |
| latency | 2 | 41 | 42 | — | — | — | 0 |
| throughput | 2 | — | — | 13528367.3 | 13528367.3 | 4509546.0 | 0 |
| latency | 3 | 41 | 42 | — | — | — | 0 |
| throughput | 3 | — | — | 13444852.1 | 13444852.1 | 4481707.0 | 0 |
| latency | 4 | 41 | 42 | — | — | — | 0 |
| throughput | 4 | — | — | 13140533.7 | 13140533.7 | 4380265.5 | 0 |
| latency | 5 | 41 | 42 | — | — | — | 0 |
| throughput | 5 | — | — | 13185509.7 | 13185509.7 | 4395257.8 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 1 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 1 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 2 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 2 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 2 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 3 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 3 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 3 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 4 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 4 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 4 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 5 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 5 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 5 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## mixed / capacity 10000

One working order at a time: sell10, buy limit3, buy market2, cancel5, then bid7/cancel.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 5000 → 5000; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 41 | 42 | — | — | — | 0 |
| throughput | 1 | — | — | 13270885.9 | 13270885.9 | 4423717.1 | 0 |
| latency | 2 | 41 | 42 | — | — | — | 0 |
| throughput | 2 | — | — | 13158976.9 | 13158976.9 | 4386413.4 | 0 |
| latency | 3 | 41 | 42 | — | — | — | 0 |
| throughput | 3 | — | — | 13235682.2 | 13235682.2 | 4411982.3 | 0 |
| latency | 4 | 41 | 42 | — | — | — | 0 |
| throughput | 4 | — | — | 13421242.5 | 13421242.5 | 4473837.0 | 0 |
| latency | 5 | 41 | 42 | — | — | — | 0 |
| throughput | 5 | — | — | 13004887.1 | 13004887.1 | 4335049.1 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 1 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 1 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 2 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 2 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 2 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 3 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 3 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 3 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 4 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 4 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 4 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |
| 5 | limit / accepted / none | 50000 | 41 | 42 (below sample threshold) |
| 5 | market / accepted / none | 16667 | 0 | 42 (below sample threshold) |
| 5 | cancel / accepted / none | 33333 | 42 | 42 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## sweep / capacity 1000

Buy markets sweep a working ask ladder. Each cycle has working_depth adds and one sweep; whole-stream throughput is not sweep-only throughput.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 500 → 530; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 42 | 1375 | — | — | — | 0 |
| throughput | 1 | — | — | 8021926.2 | 8021926.2 | 7896142.4 | 0 |
| latency | 2 | 42 | 1375 | — | — | — | 0 |
| throughput | 2 | — | — | 8201006.7 | 8201006.7 | 8072414.9 | 0 |
| latency | 3 | 42 | 1375 | — | — | — | 0 |
| throughput | 3 | — | — | 8122789.9 | 8122789.9 | 7995424.6 | 0 |
| latency | 4 | 42 | 1375 | — | — | — | 0 |
| throughput | 4 | — | — | 8349917.0 | 8349917.0 | 8218990.3 | 0 |
| latency | 5 | 42 | 1417 | — | — | — | 0 |
| throughput | 5 | — | — | 8157105.9 | 8157105.9 | 8029202.4 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 98462 | 42 | 84 (below sample threshold) |
| 1 | market / accepted / none | 1538 | 1416 | 1917 (below sample threshold) |
| 2 | limit / accepted / none | 98462 | 42 | 84 (below sample threshold) |
| 2 | market / accepted / none | 1538 | 1416 | 1958 (below sample threshold) |
| 3 | limit / accepted / none | 98462 | 42 | 84 (below sample threshold) |
| 3 | market / accepted / none | 1538 | 1416 | 1834 (below sample threshold) |
| 4 | limit / accepted / none | 98462 | 42 | 84 (below sample threshold) |
| 4 | market / accepted / none | 1538 | 1416 | 1875 (below sample threshold) |
| 5 | limit / accepted / none | 98462 | 42 | 84 (below sample threshold) |
| 5 | market / accepted / none | 1538 | 1417 | 1917 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.

## sweep / capacity 10000

Buy markets sweep a working ask ladder. Each cycle has working_depth adds and one sweep; whole-stream throughput is not sweep-only throughput.

Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. Setup background orders remain passive; this is not a full-capacity pressure test. The trace may stop partway through its final cycle; actual ending depth is reported.

Commands: 100000; rounds per mode: 5; live orders setup → end: 5000 → 5030; rejection fraction: 0.0000%.

| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| latency | 1 | 42 | 1458 | — | — | — | 0 |
| throughput | 1 | — | — | 8276233.5 | 8276233.5 | 8146462.2 | 0 |
| latency | 2 | 41 | 1500 | — | — | — | 0 |
| throughput | 2 | — | — | 8335272.7 | 8335272.7 | 8204575.6 | 0 |
| latency | 3 | 41 | 1459 | — | — | — | 0 |
| throughput | 3 | — | — | 8357506.0 | 8357506.0 | 8226460.3 | 0 |
| latency | 4 | 41 | 1459 | — | — | — | 0 |
| throughput | 4 | — | — | 8403655.1 | 8403655.1 | 8271885.8 | 0 |
| latency | 5 | 41 | 1459 | — | — | — | 0 |
| throughput | 5 | — | — | 8440302.2 | 8440302.2 | 8307958.3 | 0 |

### Latency by command and outcome

| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |
| --- | --- | --- | --- | --- |
| 1 | limit / accepted / none | 98462 | 41 | 42 (below sample threshold) |
| 1 | market / accepted / none | 1538 | 1458 | 2000 (below sample threshold) |
| 2 | limit / accepted / none | 98462 | 41 | 42 (below sample threshold) |
| 2 | market / accepted / none | 1538 | 1500 | 2083 (below sample threshold) |
| 3 | limit / accepted / none | 98462 | 41 | 42 (below sample threshold) |
| 3 | market / accepted / none | 1538 | 1500 | 2000 (below sample threshold) |
| 4 | limit / accepted / none | 98462 | 41 | 42 (below sample threshold) |
| 4 | market / accepted / none | 1538 | 1500 | 2041 (below sample threshold) |
| 5 | limit / accepted / none | 98462 | 41 | 42 (below sample threshold) |
| 5 | market / accepted / none | 1538 | 1500 | 2000 (below sample threshold) |

Resource scope: CPU deltas include the timed loop and harness; RSS is process high-water mark including verification, parsed input, warmup and earlier rounds. macOS bytes; Linux KiB converted to bytes.

Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.
