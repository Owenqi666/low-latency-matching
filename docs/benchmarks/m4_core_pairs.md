# M4 paired core report

Evidence note: this table is copied from the verified Linux `core-run-1`
report. The adjacent [full JSON](m4_core_pairs.json) is byte-identical to that
run's `pair-summary.json` (SHA-256 `2faff8258d13781fb3fc1e17b76414e8e6be1d6f19c1262537f40bb038e8942c`). Its
`/home/m2/m4-measurement/core-run-1/...` paths are original source locations,
not public download URLs. The host independently recomputed the report after
copying all 793 recorded files; only the five report directory fields changed
on relocation. The core and service experiments are independently verified;
final delivery is governed by the release acceptance/publication receipts,
and these files do not claim a published M4 Release. See
[interpretation and limits](../m4_report.md).

Mode: formal; validated 25 pairs / 100 timing intervals.

Core numerical rules only. Adoption also requires service delivery/tails, correctness, startup, memory and complexity assessment.

Each pair has independent single-run Reference/warmup and latency/throughput intervals. Short batch durations and 100000 samples do not remove noise or prove tail stability.

| Scenario | Pair | A completed/s | B completed/s | B/A − 1 | A batch ms | B batch ms | A p99 ns | B p99 ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed | 1 | 12841347.1 | 13537956.8 | +5.42% | 7.787 | 7.387 | 84 | 84 |
| mixed | 2 | 12764240.5 | 13433239.0 | +5.24% | 7.834 | 7.444 | 84 | 84 |
| mixed | 3 | 12637946.3 | 12898975.0 | +2.07% | 7.913 | 7.753 | 84 | 84 |
| mixed | 4 | 13003317.8 | 13577708.6 | +4.42% | 7.690 | 7.365 | 84 | 84 |
| mixed | 5 | 11731225.0 | 13336349.1 | +13.68% | 8.524 | 7.498 | 84 | 84 |
| cancel_heavy | 1 | 13077786.4 | 13495937.8 | +3.20% | 7.647 | 7.410 | 84 | 84 |
| cancel_heavy | 2 | 13163936.3 | 13520646.6 | +2.71% | 7.597 | 7.396 | 84 | 84 |
| cancel_heavy | 3 | 12945664.2 | 13074512.0 | +1.00% | 7.725 | 7.648 | 84 | 84 |
| cancel_heavy | 4 | 12927046.6 | 13281000.9 | +2.74% | 7.736 | 7.530 | 125 | 84 |
| cancel_heavy | 5 | 13168417.3 | 12892881.6 | -2.09% | 7.594 | 7.756 | 84 | 84 |
| sweep | 1 | 8143217.7 | 8770523.5 | +7.70% | 12.280 | 11.402 | 1125 | 1000 |
| sweep | 2 | 8307148.5 | 8786514.7 | +5.77% | 12.038 | 11.381 | 1125 | 1333 |
| sweep | 3 | 8351288.6 | 8793403.5 | +5.29% | 11.974 | 11.372 | 1375 | 1000 |
| sweep | 4 | 8090239.8 | 8682916.2 | +7.33% | 12.361 | 11.517 | 1125 | 1041 |
| sweep | 5 | 8295348.2 | 8811483.3 | +6.22% | 12.055 | 11.349 | 1166 | 1000 |
| clustered | 1 | 10441273.3 | 11095902.3 | +6.27% | 9.577 | 9.012 | 583 | 500 |
| clustered | 2 | 10827537.9 | 11239266.2 | +3.80% | 9.236 | 8.897 | 583 | 500 |
| clustered | 3 | 10527285.4 | 10786903.5 | +2.47% | 9.499 | 9.271 | 583 | 541 |
| clustered | 4 | 10879122.3 | 9638209.6 | -11.41% | 9.192 | 10.375 | 542 | 583 |
| clustered | 5 | 10694234.4 | 11186305.5 | +4.60% | 9.351 | 8.940 | 583 | 500 |
| near_full_reuse | 1 | 13216281.1 | 13602651.3 | +2.92% | 7.566 | 7.352 | 84 | 84 |
| near_full_reuse | 2 | 13186074.8 | 13446945.7 | +1.98% | 7.584 | 7.437 | 84 | 84 |
| near_full_reuse | 3 | 12786010.3 | 11217782.2 | -12.27% | 7.821 | 8.914 | 84 | 84 |
| near_full_reuse | 4 | 8465945.3 | 10558037.7 | +24.71% | 11.812 | 9.471 | 125 | 84 |
| near_full_reuse | 5 | 7433090.7 | 5660470.5 | -23.85% | 13.453 | 17.666 | 250 | 250 |

Full accepted/rejected/trades rates, counts, latency groups, CPU/RSS, clocks, input and source identities are retained in pair-summary.json and each raw run.
