# M5 ITCH interval records

Source: `7cea5df6d25c69a99831ed6b00a1babbbf151052`, clean Linux Release. These are all 30 measured intervals and six independent warmups from the frozen matrix; no interval is omitted. Each traverses its scenario input once: 1,000,000 payload messages, including 800,000 target update messages. Warmups do not enter the five-round statistics.

Values below are derived from `m5-formal/report.json`, the interval `result.json` files and their `benchmark.log` output-write measurements. The path column is relative to `m5-formal/runs/`. CPU columns are interval deltas. RSS columns are whole-process high-water marks after input loading, timing and final snapshot; construction high-water equaled input high-water in every interval. MiB means 1,048,576 bytes. These RSS values are not isolated book allocations.

| Scenario / mode / interval | Wall ms | User CPU µs | System CPU µs | M messages/s | M target updates/s | MB/s | RSS input / timed / final MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| mixed/decode/warmup | 72.095492 | 71894 | 204 | 13.870493 | 11.096394 | 455.854910 | 34.375 / 34.375 / 34.375 |
| mixed/decode/round_1 | 71.333075 | 70874 | 462 | 14.018742 | 11.214994 | 460.727145 | 34.375 / 34.375 / 34.375 |
| mixed/decode/round_2 | 71.198992 | 71201 | 0 | 14.045143 | 11.236114 | 461.594793 | 34.375 / 34.375 / 34.375 |
| mixed/decode/round_3 | 72.632908 | 72617 | 19 | 13.767864 | 11.014291 | 452.482007 | 34.375 / 34.375 / 34.375 |
| mixed/decode/round_4 | 72.624866 | 72253 | 363 | 13.769389 | 11.015511 | 452.532112 | 34.375 / 34.375 / 34.375 |
| mixed/decode/round_5 | 71.174992 | 71092 | 84 | 14.049879 | 11.239903 | 461.750442 | 34.375 / 34.375 / 34.375 |
| mixed/rebuild/warmup | 147.079146 | 147085 | 0 | 6.799060 | 5.439248 | 223.451692 | 34.375 / 34.375 / 34.500 |
| mixed/rebuild/round_1 | 146.876729 | 146499 | 364 | 6.808430 | 5.446744 | 223.759640 | 34.375 / 34.375 / 34.500 |
| mixed/rebuild/round_2 | 149.556934 | 149142 | 383 | 6.686417 | 5.349133 | 219.749651 | 34.375 / 34.375 / 34.500 |
| mixed/rebuild/round_3 | 146.126147 | 146106 | 0 | 6.843402 | 5.474722 | 224.908989 | 34.375 / 34.375 / 34.500 |
| mixed/rebuild/round_4 | 146.384188 | 145907 | 455 | 6.831339 | 5.465071 | 224.512527 | 34.375 / 34.375 / 34.500 |
| mixed/rebuild/round_5 | 149.440809 | 149195 | 232 | 6.691613 | 5.353290 | 219.920410 | 34.375 / 34.375 / 34.500 |
| cancel_replace/decode/warmup | 70.033952 | 69662 | 374 | 14.278789 | 11.423031 | 465.212887 | 34.125 / 34.125 / 34.125 |
| cancel_replace/decode/round_1 | 70.082245 | 69508 | 576 | 14.268949 | 11.415159 | 464.892313 | 34.125 / 34.125 / 34.125 |
| cancel_replace/decode/round_2 | 70.196244 | 70198 | 0 | 14.245776 | 11.396621 | 464.137326 | 34.125 / 34.125 / 34.125 |
| cancel_replace/decode/round_3 | 70.708951 | 70712 | 0 | 14.142481 | 11.313985 | 460.771890 | 34.125 / 34.125 / 34.125 |
| cancel_replace/decode/round_4 | 70.457619 | 70461 | 0 | 14.192929 | 11.354343 | 462.415527 | 34.125 / 34.125 / 34.125 |
| cancel_replace/decode/round_5 | 70.965909 | 70968 | 0 | 14.091273 | 11.273018 | 459.103497 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/warmup | 133.681163 | 133452 | 219 | 7.480485 | 5.984388 | 243.719431 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/round_1 | 137.277908 | 137280 | 0 | 7.284493 | 5.827595 | 237.333869 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/round_2 | 135.417452 | 134875 | 544 | 7.384573 | 5.907658 | 240.594521 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/round_3 | 134.627328 | 134467 | 164 | 7.427912 | 5.942330 | 242.006563 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/round_4 | 135.446578 | 135444 | 0 | 7.382985 | 5.906388 | 240.542784 | 34.125 / 34.125 / 34.125 |
| cancel_replace/rebuild/round_5 | 136.486409 | 136489 | 0 | 7.326737 | 5.861389 | 238.710193 | 34.125 / 34.125 / 34.125 |
| multilevel/decode/warmup | 71.465992 | 71345 | 124 | 13.992669 | 11.194136 | 455.035802 | 34.000 / 34.000 / 34.000 |
| multilevel/decode/round_1 | 71.917367 | 71679 | 230 | 13.904847 | 11.123878 | 452.179861 | 34.000 / 34.000 / 34.000 |
| multilevel/decode/round_2 | 70.897785 | 70899 | 0 | 14.104813 | 11.283850 | 458.682665 | 34.000 / 34.000 / 34.000 |
| multilevel/decode/round_3 | 73.381948 | 73384 | 0 | 13.627330 | 10.901864 | 443.155107 | 34.000 / 34.000 / 34.000 |
| multilevel/decode/round_4 | 71.219575 | 71222 | 0 | 14.041084 | 11.232867 | 456.610209 | 34.000 / 34.000 / 34.000 |
| multilevel/decode/round_5 | 71.346659 | 70841 | 498 | 14.016073 | 11.212859 | 455.796886 | 34.000 / 34.000 / 34.000 |
| multilevel/rebuild/warmup | 168.021995 | 168002 | 0 | 5.951602 | 4.761281 | 193.543619 | 34.000 / 34.125 / 34.250 |
| multilevel/rebuild/round_1 | 166.170622 | 166163 | 0 | 6.017911 | 4.814329 | 195.699966 | 34.000 / 34.125 / 34.250 |
| multilevel/rebuild/round_2 | 165.378456 | 164843 | 539 | 6.046737 | 4.837389 | 196.637372 | 34.000 / 34.125 / 34.250 |
| multilevel/rebuild/round_3 | 168.960951 | 168577 | 376 | 5.918527 | 4.734822 | 192.468051 | 34.000 / 34.125 / 34.250 |
| multilevel/rebuild/round_4 | 164.471540 | 164474 | 0 | 6.080079 | 4.864063 | 197.721654 | 34.000 / 34.125 / 34.250 |
| multilevel/rebuild/round_5 | 166.319996 | 166323 | 0 | 6.012506 | 4.810005 | 195.524205 | 34.000 / 34.125 / 34.250 |

## Excluded work and clock observations

Input reads, construction, EOF/context validation (`finish`), final snapshot/checksum and output writing are outside the timed loop. Reference validation runs before any interval and is also excluded. The reader's whole-input FNV-1a pass and decoded-field checksum consumption are inside the loop. The steady clock reports a nominal 1 ns period, but every interval's 10,000-pair preflight observed a minimum positive 41 ns; zero observations are shown below. A zero snapshot duration in decode mode means no order-book snapshot work at this clock resolution. None of these batch durations is a per-message latency percentile.

| Scenario / mode / interval | Input read ms | Construct ns | Finish ns | Snapshot ns | Output write ns | Zero clock pairs / 10000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed/decode/warmup | 6.917241 | 1000 | 292 | 41 | 89208 | 6217 |
| mixed/decode/round_1 | 6.686367 | 583 | 208 | 0 | 109792 | 6800 |
| mixed/decode/round_2 | 6.819950 | 834 | 292 | 42 | 103792 | 7144 |
| mixed/decode/round_3 | 7.138991 | 958 | 167 | 42 | 98166 | 6083 |
| mixed/decode/round_4 | 6.753199 | 709 | 250 | 0 | 95833 | 6854 |
| mixed/decode/round_5 | 7.122741 | 959 | 292 | 42 | 89416 | 6318 |
| mixed/rebuild/warmup | 6.923908 | 1458 | 166 | 76500 | 89834 | 6726 |
| mixed/rebuild/round_1 | 6.814158 | 1500 | 166 | 88375 | 88791 | 6718 |
| mixed/rebuild/round_2 | 6.873658 | 1708 | 167 | 78375 | 89583 | 6751 |
| mixed/rebuild/round_3 | 6.701200 | 1250 | 125 | 77500 | 86125 | 6559 |
| mixed/rebuild/round_4 | 6.628242 | 1042 | 167 | 75042 | 94042 | 6431 |
| mixed/rebuild/round_5 | 6.888491 | 1666 | 42 | 82166 | 101458 | 7168 |
| cancel_replace/decode/warmup | 6.574741 | 542 | 333 | 0 | 96208 | 6925 |
| cancel_replace/decode/round_1 | 6.636200 | 916 | 250 | 0 | 87792 | 6417 |
| cancel_replace/decode/round_2 | 6.508450 | 666 | 250 | 42 | 96500 | 6429 |
| cancel_replace/decode/round_3 | 6.751450 | 542 | 334 | 0 | 95417 | 6503 |
| cancel_replace/decode/round_4 | 6.916366 | 584 | 334 | 41 | 122959 | 6688 |
| cancel_replace/decode/round_5 | 6.873199 | 667 | 334 | 0 | 88750 | 6448 |
| cancel_replace/rebuild/warmup | 6.840992 | 1375 | 167 | 1667 | 100584 | 6404 |
| cancel_replace/rebuild/round_1 | 6.545159 | 1459 | 84 | 1583 | 95292 | 6649 |
| cancel_replace/rebuild/round_2 | 6.590200 | 1458 | 125 | 2000 | 117833 | 7013 |
| cancel_replace/rebuild/round_3 | 7.091866 | 1583 | 166 | 1625 | 112958 | 7214 |
| cancel_replace/rebuild/round_4 | 6.539241 | 833 | 125 | 1541 | 95792 | 6225 |
| cancel_replace/rebuild/round_5 | 6.643617 | 1292 | 83 | 1375 | 115167 | 6995 |
| multilevel/decode/warmup | 7.007408 | 542 | 334 | 41 | 100458 | 6274 |
| multilevel/decode/round_1 | 6.721450 | 709 | 292 | 42 | 91249 | 7014 |
| multilevel/decode/round_2 | 6.525325 | 709 | 167 | 41 | 87208 | 7215 |
| multilevel/decode/round_3 | 6.510408 | 750 | 292 | 0 | 107750 | 7146 |
| multilevel/decode/round_4 | 6.793575 | 584 | 250 | 0 | 86042 | 6282 |
| multilevel/decode/round_5 | 6.655450 | 583 | 292 | 41 | 90000 | 6405 |
| multilevel/rebuild/warmup | 7.062407 | 1709 | 166 | 95208 | 81458 | 6583 |
| multilevel/rebuild/round_1 | 6.579533 | 958 | 125 | 92542 | 83292 | 6551 |
| multilevel/rebuild/round_2 | 6.656700 | 1416 | 42 | 106458 | 93625 | 6624 |
| multilevel/rebuild/round_3 | 6.839741 | 1708 | 125 | 111084 | 79583 | 6897 |
| multilevel/rebuild/round_4 | 6.710241 | 1292 | 125 | 102000 | 81749 | 6786 |
| multilevel/rebuild/round_5 | 6.720992 | 1458 | 250 | 105499 | 88709 | 6706 |

In decode mode, target updates/s counts decoded target update messages; no updates are applied to an order book. In rebuild mode those messages are applied. MB/s uses decimal bytes. Mode subtraction does not isolate reconstruction cost. See [the report](../m5_report.md) for input composition, source identity and measurement limitations.
