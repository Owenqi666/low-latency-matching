# M2 corrected service rounds

Source `eb0a109b026c8ac9cf48d987163fad8751980047`. All 35 measured rounds below derive from the independently
validated source report whose SHA-256 is `33d196edac8be2a0554ab5945e0099d4d6536bff8c55fd3d92fc63b44918643f`.
The original guest and independent host reports match. The
[JSON companion](m2_service_rounds.json) retains exact nanoseconds, all seven
warmups, per-kind/outcome RTT populations, queue/delivery counters, Reference
bindings, input metadata and source/environment hashes. See the
[main report](../m2_report.md) for interpretation and the retained first matrix.

## Per-round timing

Latency columns are microseconds. RTT N is client completions; service N includes
all internally completed measured admissions, even if their client disconnected.
Send-lag p99 uses started requests; Gateway p99 uses the service population.
The threshold means 100000 completed client samples and at least ten seconds,
not statistical stability. All failed rounds remain visible.

| Row / round | Outcome / samples | RTT N | RTT p50 us | RTT p99 us | Service N | Service p50 us | Service p99 us | Lag p99 us | Gateway p99 us | Window s | Complete/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 / 1 | completed / threshold met | 100001 | 65.667 | 90.376 | 100001 | 14.542 | 22.334 | 27.629 | 0.209 | 10.000074 | 10000.026 |
| mixed_4 / 2 | completed / threshold met | 100001 | 65.376 | 93.125 | 100001 | 14.583 | 22.417 | 28.583 | 0.208 | 10.000076 | 10000.024 |
| mixed_4 / 3 | completed / threshold met | 100001 | 64.501 | 90.292 | 100001 | 14.542 | 22.292 | 27.390 | 0.209 | 10.000073 | 10000.027 |
| mixed_4 / 4 | completed / threshold met | 100001 | 66.375 | 93.543 | 100001 | 14.459 | 22.500 | 28.163 | 0.208 | 10.000087 | 10000.013 |
| mixed_4 / 5 | completed / threshold met | 100001 | 62.833 | 92.084 | 100001 | 14.416 | 25.000 | 30.423 | 0.209 | 10.000080 | 10000.020 |
| cancel_heavy_4 / 1 | completed / threshold met | 100001 | 59.959 | 81.250 | 100001 | 14.334 | 24.875 | 26.995 | 0.209 | 10.000075 | 10000.025 |
| cancel_heavy_4 / 2 | completed / threshold met | 100001 | 60.959 | 105.626 | 100001 | 14.708 | 25.708 | 33.966 | 0.209 | 10.000124 | 9999.976 |
| cancel_heavy_4 / 3 | completed / threshold met | 100001 | 60.959 | 120.668 | 100001 | 14.750 | 27.375 | 41.045 | 0.250 | 10.000077 | 10000.023 |
| cancel_heavy_4 / 4 | completed / threshold met | 100001 | 60.625 | 90.625 | 100001 | 14.458 | 22.542 | 28.148 | 0.209 | 10.000070 | 10000.030 |
| cancel_heavy_4 / 5 | completed / threshold met | 100001 | 60.834 | 90.917 | 100001 | 14.833 | 23.083 | 30.587 | 0.209 | 10.000076 | 10000.024 |
| sweep_4 / 1 | completed / threshold met | 100001 | 61.083 | 205.126 | 100001 | 14.875 | 26.666 | 27.488 | 0.209 | 10.000078 | 10000.022 |
| sweep_4 / 2 | completed / threshold met | 100001 | 60.792 | 203.917 | 100001 | 14.625 | 27.292 | 30.965 | 0.208 | 10.000079 | 10000.021 |
| sweep_4 / 3 | completed / threshold met | 100001 | 60.833 | 219.418 | 100001 | 14.500 | 26.625 | 36.370 | 0.208 | 10.000078 | 10000.022 |
| sweep_4 / 4 | completed / threshold met | 100001 | 60.250 | 223.959 | 100001 | 14.375 | 36.625 | 63.614 | 0.417 | 10.000076 | 10000.024 |
| sweep_4 / 5 | completed / threshold met | 100001 | 60.209 | 217.250 | 100001 | 14.334 | 26.334 | 36.854 | 0.208 | 10.000082 | 10000.018 |
| burst_4 / 1 | completed / threshold met | 100000 | 2013.088 | 4689.223 | 100000 | 24.042 | 198.459 | 9515.913 | 22.542 | 49.910202 | 2003.598 |
| burst_4 / 2 | completed / threshold met | 100000 | 1744.252 | 4166.801 | 100000 | 20.708 | 177.875 | 5090.739 | 18.375 | 49.910141 | 2003.601 |
| burst_4 / 3 | completed / threshold met | 100000 | 1754.544 | 4104.753 | 100000 | 20.584 | 207.250 | 5092.469 | 18.750 | 49.911826 | 2003.533 |
| burst_4 / 4 | completed / threshold met | 100000 | 2001.376 | 5100.250 | 100000 | 21.250 | 475.625 | 5123.878 | 28.125 | 49.910985 | 2003.567 |
| burst_4 / 5 | completed / threshold met | 100000 | 1869.332 | 4236.875 | 100000 | 20.875 | 266.000 | 5055.123 | 20.750 | 49.911769 | 2003.535 |
| mixed_1 / 1 | completed / threshold met | 100001 | 61.541 | 83.125 | 100001 | 14.541 | 22.083 | 28.560 | 0.209 | 10.000072 | 10000.028 |
| mixed_1 / 2 | completed / threshold met | 100001 | 61.000 | 82.042 | 100001 | 14.458 | 22.083 | 27.095 | 0.208 | 10.000074 | 10000.026 |
| mixed_1 / 3 | completed / threshold met | 100001 | 60.625 | 80.875 | 100001 | 14.250 | 21.958 | 28.037 | 0.250 | 10.000078 | 10000.022 |
| mixed_1 / 4 | completed / threshold met | 100001 | 61.250 | 93.291 | 100001 | 14.500 | 23.209 | 30.366 | 0.209 | 10.000072 | 10000.028 |
| mixed_1 / 5 | completed / threshold met | 100001 | 61.750 | 85.583 | 100001 | 14.625 | 22.666 | 28.770 | 0.208 | 10.000078 | 10000.022 |
| mixed_4_near / 1 | completed / threshold met | 450001 | 70.584 | 151.624 | 450001 | 11.042 | 22.208 | 38.755 | 3.916 | 10.000070 | 44999.783 |
| mixed_4_near / 2 | completed / threshold met | 450001 | 70.500 | 154.875 | 450001 | 11.000 | 21.833 | 38.682 | 3.875 | 10.000083 | 44999.727 |
| mixed_4_near / 3 | completed / threshold met | 450001 | 70.625 | 207.916 | 450001 | 10.959 | 24.166 | 40.454 | 4.000 | 10.000048 | 44999.882 |
| mixed_4_near / 4 | completed / threshold met | 450001 | 66.709 | 144.666 | 450001 | 10.834 | 20.750 | 35.939 | 3.750 | 10.000090 | 44999.694 |
| mixed_4_near / 5 | completed / threshold met | 450001 | 66.209 | 136.124 | 450001 | 10.750 | 20.458 | 34.609 | 3.709 | 10.000054 | 44999.858 |
| mixed_4_overload / 1 | failed / threshold met | 201000 | 59.291 | 120.041 | 201307 | 10.334 | 22.416 | 31.086 | 4.500 | 10.000051 | 20099.898 |
| mixed_4_overload / 2 | failed / below threshold | 1281 | 1843.496 | 4890.449 | 1694 | 8.459 | 16.917 | 211.837 | 3.792 | 10.000001 | 128.100 |
| mixed_4_overload / 3 | failed / threshold met | 200953 | 58.708 | 111.999 | 201259 | 10.292 | 22.292 | 32.459 | 4.499 | 10.000047 | 20095.206 |
| mixed_4_overload / 4 | failed / threshold met | 400599 | 68.416 | 137.083 | 400805 | 8.709 | 21.750 | 34.744 | 4.334 | 10.000038 | 40059.749 |
| mixed_4_overload / 5 | failed / threshold met | 200931 | 60.291 | 167.374 | 201242 | 11.084 | 33.292 | 32.485 | 4.708 | 10.000090 | 20092.920 |

## Request accounting

All columns exclude setup. Complete includes business rejections. Full writes
mean local complete-frame write callbacks, not peer receipt. Admissions can
exceed client Completes when delivery fails. Every row satisfies planned =
not-started + started and started = complete + failed + unfinished.

| Row / round | Planned | Not started | Started | Complete | Failed | Unfinished | Accepted | Rejected | Full writes | Actual admissions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 / 1 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_4 / 2 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_4 / 3 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_4 / 4 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_4 / 5 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| cancel_heavy_4 / 1 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 97562 | 2439 | 100001 | 100001 |
| cancel_heavy_4 / 2 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 97562 | 2439 | 100001 | 100001 |
| cancel_heavy_4 / 3 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 97562 | 2439 | 100001 | 100001 |
| cancel_heavy_4 / 4 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 97562 | 2439 | 100001 | 100001 |
| cancel_heavy_4 / 5 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 97562 | 2439 | 100001 | 100001 |
| sweep_4 / 1 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| sweep_4 / 2 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| sweep_4 / 3 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| sweep_4 / 4 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| sweep_4 / 5 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| burst_4 / 1 | 100000 | 0 | 100000 | 100000 | 0 | 0 | 100000 | 0 | 100000 | 100000 |
| burst_4 / 2 | 100000 | 0 | 100000 | 100000 | 0 | 0 | 100000 | 0 | 100000 | 100000 |
| burst_4 / 3 | 100000 | 0 | 100000 | 100000 | 0 | 0 | 100000 | 0 | 100000 | 100000 |
| burst_4 / 4 | 100000 | 0 | 100000 | 100000 | 0 | 0 | 100000 | 0 | 100000 | 100000 |
| burst_4 / 5 | 100000 | 0 | 100000 | 100000 | 0 | 0 | 100000 | 0 | 100000 | 100000 |
| mixed_1 / 1 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_1 / 2 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_1 / 3 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_1 / 4 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_1 / 5 | 100001 | 0 | 100001 | 100001 | 0 | 0 | 100001 | 0 | 100001 | 100001 |
| mixed_4_near / 1 | 450001 | 0 | 450001 | 450001 | 0 | 0 | 450001 | 0 | 450001 | 450001 |
| mixed_4_near / 2 | 450001 | 0 | 450001 | 450001 | 0 | 0 | 450001 | 0 | 450001 | 450001 |
| mixed_4_near / 3 | 450001 | 0 | 450001 | 450001 | 0 | 0 | 450001 | 0 | 450001 | 450001 |
| mixed_4_near / 4 | 450001 | 0 | 450001 | 450001 | 0 | 0 | 450001 | 0 | 450001 | 450001 |
| mixed_4_near / 5 | 450001 | 0 | 450001 | 450001 | 0 | 0 | 450001 | 0 | 450001 | 450001 |
| mixed_4_overload / 1 | 800001 | 598693 | 201308 | 201000 | 308 | 0 | 201000 | 0 | 201307 | 201307 |
| mixed_4_overload / 2 | 800001 | 798304 | 1697 | 1281 | 416 | 0 | 1281 | 0 | 1696 | 1694 |
| mixed_4_overload / 3 | 800001 | 598741 | 201260 | 200953 | 307 | 0 | 200953 | 0 | 201260 | 201259 |
| mixed_4_overload / 4 | 800001 | 399196 | 400805 | 400599 | 206 | 0 | 400599 | 0 | 400805 | 400805 |
| mixed_4_overload / 5 | 800001 | 598757 | 201244 | 200931 | 313 | 0 | 200931 | 0 | 201243 | 201242 |

## Resources and delivery

CPU is server user/system seconds across startup, setup, measured workload and
shutdown. RSS is MiB captured before evidence formatting. HWM columns are command
slots / event slots / outgoing wire bytes. Missing/discarded counts are business
recipient frames, not a count of unique requests. These counters include setup.

| Row / round | CPU user/system s | RSS MiB | HWM cmd/event/send | Output waits | Slow closes | Missing business | Discarded business |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 / 1 | 0.773014/3.393485 | 36.613 | 3/12/1416 | 0 | 0 | 0 | 0 |
| mixed_4 / 2 | 0.754301/3.400787 | 37.414 | 3/12/1416 | 0 | 0 | 0 | 0 |
| mixed_4 / 3 | 0.858276/3.278683 | 37.461 | 2/8/944 | 0 | 0 | 0 | 0 |
| mixed_4 / 4 | 0.749160/3.442694 | 37.461 | 3/12/1612 | 0 | 0 | 0 | 0 |
| mixed_4 / 5 | 0.912111/3.101279 | 37.465 | 4/16/1474 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 / 1 | 0.900692/2.344621 | 37.465 | 2/8/966 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 / 2 | 0.702515/2.595835 | 37.469 | 3/9/886 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 / 3 | 0.839963/2.438167 | 37.473 | 3/10/1380 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 / 4 | 0.726933/2.536164 | 37.488 | 2/8/1104 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 / 5 | 0.384620/2.932072 | 37.488 | 4/12/1300 | 0 | 0 | 0 | 0 |
| sweep_4 / 1 | 0.635819/2.887682 | 38.219 | 3/74/9638 | 0 | 0 | 0 | 0 |
| sweep_4 / 2 | 0.689341/2.783310 | 38.219 | 8/80/10466 | 0 | 0 | 0 | 0 |
| sweep_4 / 3 | 0.364413/3.197472 | 39.004 | 3/73/9994 | 0 | 0 | 0 | 0 |
| sweep_4 / 4 | 0.810280/2.713499 | 39.004 | 17/86/10408 | 0 | 0 | 0 | 0 |
| sweep_4 / 5 | 0.514316/2.935365 | 39.004 | 2/70/9580 | 0 | 0 | 0 | 0 |
| burst_4 / 1 | 0.894574/2.794736 | 39.129 | 176/237/33370 | 0 | 0 | 0 | 0 |
| burst_4 / 2 | 1.007270/3.211221 | 39.129 | 90/193/24784 | 0 | 0 | 0 | 0 |
| burst_4 / 3 | 0.971988/3.232425 | 39.129 | 101/287/23964 | 0 | 0 | 0 | 0 |
| burst_4 / 4 | 1.118412/3.103828 | 39.129 | 199/787/32926 | 0 | 0 | 0 | 0 |
| burst_4 / 5 | 1.010650/3.198635 | 39.129 | 127/506/24354 | 0 | 0 | 0 | 0 |
| mixed_1 / 1 | 0.825419/2.545697 | 39.129 | 2/8/1082 | 0 | 0 | 0 | 0 |
| mixed_1 / 2 | 0.962037/2.382615 | 39.129 | 7/28/3304 | 0 | 0 | 0 | 0 |
| mixed_1 / 3 | 0.699722/2.565648 | 39.129 | 3/12/1416 | 0 | 0 | 0 | 0 |
| mixed_1 / 4 | 0.764091/2.613541 | 39.129 | 24/96/11328 | 0 | 0 | 0 | 0 |
| mixed_1 / 5 | 0.753383/2.646763 | 39.129 | 4/16/1888 | 0 | 0 | 0 | 0 |
| mixed_4_near / 1 | 2.390503/8.638648 | 106.863 | 11/43/4196 | 0 | 0 | 0 | 0 |
| mixed_4_near / 2 | 2.134232/8.886767 | 106.996 | 13/65/5184 | 0 | 0 | 0 | 0 |
| mixed_4_near / 3 | 2.223110/8.752472 | 107.035 | 41/102/42318 | 0 | 0 | 0 | 0 |
| mixed_4_near / 4 | 2.048329/8.813993 | 107.039 | 32/65/8508 | 0 | 0 | 0 | 0 |
| mixed_4_near / 5 | 2.552307/8.283879 | 107.039 | 11/53/2882 | 0 | 0 | 0 | 0 |
| mixed_4_overload / 1 | 0.884680/2.758121 | 176.109 | 9/35/65486 | 0 | 3 | 4 | 918 |
| mixed_4_overload / 2 | 0.007183/0.036944 | 176.156 | 13/52/65516 | 0 | 4 | 13 | 1240 |
| mixed_4_overload / 3 | 0.656073/2.915880 | 176.156 | 6/28/65486 | 0 | 3 | 1 | 921 |
| mixed_4_overload / 4 | 1.517225/5.605305 | 176.156 | 50/134/65464 | 0 | 2 | 2 | 612 |
| mixed_4_overload / 5 | 0.572512/3.005690 | 176.160 | 25/80/65508 | 0 | 3 | 9 | 921 |

## Reference and final state

Command/Event sequences and Trade counts include the 500 setup commands in each
measured run. Final order/level counts are taken from the saved canonical snapshot.
Every successful Reference report verifies the entire actual admitted sequence,
not only the client's surviving completed subset. Failure reasons aggregate
planned client outcomes and need not equal the count of server close events.

| Row / round | Drained | Reference | Complete command seq | Last event seq | Trades | Final orders | Bid/ask levels | Client failure reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 / 1 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_4 / 2 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_4 / 3 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_4 / 4 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_4 / 5 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| cancel_heavy_4 / 1 | yes | passed | 1–100501 | 299064 | 0 | 500 | 24/8 | none |
| cancel_heavy_4 / 2 | yes | passed | 1–100501 | 299064 | 0 | 500 | 24/8 | none |
| cancel_heavy_4 / 3 | yes | passed | 1–100501 | 299064 | 0 | 500 | 24/8 | none |
| cancel_heavy_4 / 4 | yes | passed | 1–100501 | 299064 | 0 | 500 | 24/8 | none |
| cancel_heavy_4 / 5 | yes | passed | 1–100501 | 299064 | 0 | 500 | 24/8 | none |
| sweep_4 / 1 | yes | passed | 1–100501 | 398397 | 98432 | 531 | 16/4 | none |
| sweep_4 / 2 | yes | passed | 1–100501 | 398397 | 98432 | 531 | 16/4 | none |
| sweep_4 / 3 | yes | passed | 1–100501 | 398397 | 98432 | 531 | 16/4 | none |
| sweep_4 / 4 | yes | passed | 1–100501 | 398397 | 98432 | 531 | 16/4 | none |
| sweep_4 / 5 | yes | passed | 1–100501 | 398397 | 98432 | 531 | 16/4 | none |
| burst_4 / 1 | yes | passed | 1–100500 | 304984 | 43484 | 500 | 8/8 | none |
| burst_4 / 2 | yes | passed | 1–100500 | 304124 | 42624 | 500 | 8/8 | none |
| burst_4 / 3 | yes | passed | 1–100500 | 304034 | 42534 | 500 | 8/8 | none |
| burst_4 / 4 | yes | passed | 1–100500 | 304143 | 42643 | 500 | 8/8 | none |
| burst_4 / 5 | yes | passed | 1–100500 | 304180 | 42680 | 500 | 8/8 | none |
| mixed_1 / 1 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_1 / 2 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_1 / 3 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_1 / 4 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_1 / 5 | yes | passed | 1–100501 | 301503 | 40000 | 501 | 8/9 | none |
| mixed_4_near / 1 | yes | passed | 1–450501 | 1351506 | 180003 | 501 | 8/9 | none |
| mixed_4_near / 2 | yes | passed | 1–450501 | 1351510 | 180007 | 501 | 8/9 | none |
| mixed_4_near / 3 | yes | passed | 1–450501 | 1351531 | 180028 | 501 | 8/9 | none |
| mixed_4_near / 4 | yes | passed | 1–450501 | 1351515 | 180012 | 501 | 8/9 | none |
| mixed_4_near / 5 | yes | passed | 1–450501 | 1351507 | 180004 | 501 | 8/9 | none |
| mixed_4_overload / 1 | yes | passed | 1–201807 | 606692 | 81794 | 501 | 8/9 | {"disconnected": 599001} |
| mixed_4_overload / 2 | yes | passed | 1–2194 | 6587 | 683 | 502 | 8/10 | {"disconnected": 798720} |
| mixed_4_overload / 3 | yes | passed | 1–201759 | 605278 | 80505 | 501 | 9/8 | {"disconnected": 599048} |
| mixed_4_overload / 4 | yes | passed | 1–401305 | 1203924 | 160331 | 500 | 8/8 | {"disconnected": 399402} |
| mixed_4_overload / 5 | yes | passed | 1–201742 | 605227 | 80499 | 501 | 9/8 | {"disconnected": 599070} |

## Independent warmups

Each warmup has its own server and setup and contributes no formal latency sample.

| Row | Planned / completed | Client success | Server drained | Reference |
| --- | --- | --- | --- | --- |
| mixed_4 | 1000 / 1000 | True | True | passed |
| cancel_heavy_4 | 1000 / 1000 | True | True | passed |
| sweep_4 | 1000 / 1000 | True | True | passed |
| burst_4 | 1000 / 1000 | True | True | passed |
| mixed_1 | 1000 / 1000 | True | True | passed |
| mixed_4_near | 1000 / 1000 | True | True | passed |
| mixed_4_overload | 1000 / 1000 | True | True | passed |
