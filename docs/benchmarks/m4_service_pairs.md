# M4 service pairs: all 20 formal pairs

The archived independent checker recomputed all raw samples on a separate host copy. All eight derived files are byte-identical to the guest results. The original 941 files (1,132,867,731 bytes) remain unchanged; see `build/m4-measurement/service-host-revalidation.json` and `service-revalidation.log` in the permanent validation evidence.

A is list storage `97fdc6ee165201b0ab9b3997879f5296fb508d9f`; B is fixed order slots `4cf669ff2e932c6f27adeca0a9e143ffd03430b1`. Both use single-frame sends and the same load generator, verifier, workload bytes and resource limits. The [complete JSON](m4_service_pairs.json) retains every measured pair and full source/tool provenance.

This is the four-scene M4 subset, not the seven-scene M2/M3 matrix. All 40 formal attempts and eight separate warmups fully deliver, drain and pass independent Reference verification. All 40 formal attempts meet the 100,000-completion and 10-second sample rule. Each scene runs five adjacent pairs in AB/BA/AB/BA/AB order. Ordinary runs plan 100,001 requests, burst 100,000; each has 500 setup requests outside the measured stream.

Measurements are synthetic loopback traffic in the shared four-vCPU, 4-GiB QEMU/HVF Linux aarch64 guest on the Apple M5 Pro host. Frequency, exclusive cores and physical CPU affinity are not controlled. Changes are `100 × (B/A − 1)` per pair; reported medians/ranges are not pooled percentiles or confidence intervals.

Server CPU/request is lifetime user + system CPU (including setup and shutdown before evidence output) divided by completed measured requests. It is an amortized cost. RSS is process peak resident memory, not exclusive order-slot storage. Negative changes indicate a decrease.

## Paired changes

| Scene | RTT p99 median [min, max] | Service p99 median [min, max] | CPU/request median [min, max] | RTT gate |
|---|---:|---:|---:|---|
| mixed_1 | +1.60% [-38.40%, +23.04%] | -3.33% [-38.23%, +7.37%] | -0.32% [-4.72%, +4.42%] | pass |
| mixed_4 | -0.70% [-21.98%, +69.57%] | +0.71% [-9.41%, +39.47%] | -1.41% [-4.26%, +2.24%] | pass |
| sweep_4 | +1.89% [+0.53%, +5.42%] | +26.44% [-1.03%, +65.51%] | +0.31% [-0.58%, +3.39%] | pass |
| burst_4 | +0.21% [-11.38%, +1.34%] | -13.77% [-54.15%, +30.11%] | -3.63% [-6.25%, +6.31%] | pass |

All four median RTT gates pass, but individual pairs vary substantially. These service gates alone do not adopt the candidate: core throughput, correctness, initialization, memory and complexity remain separate decision inputs.

The sweep scene's internal service p99 rises by a paired median 26.44%, with four of five pairs increasing. Its absolute per-run p99 medians are 28.250 us for A and 39.375 us for B; the ratio of those two medians is a different statistic from the median paired change. Mixed four-client RTT p99 rises 69.57% in pair 3. These observations preclude a blanket claim that service latency never regressed.

The server and load-generator peak-RSS paired median changes are zero in all four scenes. These process-level observations do not establish zero memory cost for preallocated slots. Actual ordinary measurement durations are approximately 10.0001 seconds, while burst runs last 49.9101–49.9119 seconds against their 50-second average-rate plan. All ten sweep measurements record a maximum 64 trades for one command.

## Every measured pair

| Scene / pair | Order | A/B RTT p99 (us) | RTT change | A/B service p99 (us) | A/B CPU/request (us) | A/B server RSS (MiB) |
|---|---|---:|---:|---:|---:|---:|
| mixed_1-round_1 | AB | 95.287/117.245 | +23.04% | 23.749/25.499 | 33.985/35.486 | 36.363/36.500 |
| mixed_1-round_2 | BA | 171.662/105.746 | -38.40% | 43.374/26.790 | 35.871/34.179 | 36.500/36.500 |
| mixed_1-round_3 | AB | 106.123/100.790 | -5.03% | 25.041/24.208 | 35.292/34.679 | 36.516/36.516 |
| mixed_1-round_4 | BA | 93.749/95.249 | +1.60% | 26.208/23.458 | 34.161/34.074 | 36.516/36.516 |
| mixed_1-round_5 | AB | 95.499/97.291 | +1.88% | 26.042/26.375 | 34.138/34.029 | 36.516/36.516 |
| mixed_4-round_1 | AB | 100.582/99.874 | -0.70% | 23.666/23.833 | 41.380/41.171 | 36.516/36.516 |
| mixed_4-round_2 | BA | 126.042/98.333 | -21.98% | 26.125/23.666 | 43.208/41.366 | 36.516/36.516 |
| mixed_4-round_3 | AB | 102.833/174.375 | +69.57% | 23.750/33.125 | 41.866/42.805 | 36.516/36.516 |
| mixed_4-round_4 | BA | 105.876/99.918 | -5.63% | 24.417/23.750 | 42.941/41.978 | 36.516/36.516 |
| mixed_4-round_5 | AB | 117.669/125.418 | +6.59% | 26.000/26.417 | 44.027/43.408 | 36.516/36.516 |
| sweep_4-round_1 | AB | 221.585/222.878 | +0.58% | 28.250/27.959 | 36.175/36.232 | 37.109/37.168 |
| sweep_4-round_2 | BA | 221.210/222.378 | +0.53% | 27.292/27.833 | 36.061/35.852 | 37.199/37.168 |
| sweep_4-round_3 | AB | 226.877/239.169 | +5.42% | 27.667/45.792 | 36.095/37.317 | 37.207/37.207 |
| sweep_4-round_4 | BA | 229.960/237.294 | +3.19% | 34.042/43.042 | 37.528/37.865 | 37.207/37.207 |
| sweep_4-round_5 | AB | 222.335/226.543 | +1.89% | 28.625/39.375 | 36.717/36.832 | 37.207/37.207 |
| burst_4-round_1 | AB | 4413.579/3911.488 | -11.38% | 392.545/180.001 | 42.564/39.902 | 38.105/38.129 |
| burst_4-round_2 | BA | 3993.070/4006.404 | +0.33% | 148.209/146.376 | 40.452/38.984 | 38.137/38.137 |
| burst_4-round_3 | AB | 4093.027/4147.818 | +1.34% | 215.126/185.501 | 39.170/41.640 | 38.137/38.176 |
| burst_4-round_4 | BA | 4194.652/4152.318 | -1.01% | 193.458/251.709 | 42.757/40.366 | 38.223/38.195 |
| burst_4-round_5 | AB | 3970.953/3979.252 | +0.21% | 209.208/146.001 | 40.947/41.496 | 38.223/38.223 |

All formal measured streams have zero failed, unfinished, not-started or rejected requests. The JSON also preserves send lag, gateway wait, per-command outcome groups, queue/send high-water marks, write counters and client resources. The host audit records per-scene absolute medians/ranges; per-run observations remain authoritative.
