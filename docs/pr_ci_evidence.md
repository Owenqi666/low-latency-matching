# PR CI evidence for 59a2931

Verified on 2026-10-16. The completed [CI run 38971625920](https://github.com/Owenqi666/low-latency-matching/actions/runs/38971625920) has conclusion `success` and event `pull_request`.

- PR head SHA: `59a29316a8d91b33bcb5572438eb731a8bc0b96f`.
- Actual checked-out/tested PR merge SHA, identical in all three downloaded `checkout-sha.log` files: `d2aa42b91cd9466afb757130efe1d22abffcfbe5`.
- Artifacts downloaded successfully to `/Users/owen/Desktop/low_latency/build/evidence/pr-59a2931`.

| Actual job | CTest evidence | Job conclusion |
| --- | --- | --- |
| [Debug](https://github.com/Owenqi666/low-latency-matching/actions/runs/38971625920/job/117211115910) | 100% passed; 0 failed out of 59 | success |
| [Release](https://github.com/Owenqi666/low-latency-matching/actions/runs/38971625920/job/117211115591) | 100% passed; 0 failed out of 60 | success |
| [ASan/UBSan](https://github.com/Owenqi666/low-latency-matching/actions/runs/38971625920/job/117211115911) | 100% passed; 0 failed out of 59 | success |

Each artifact includes actual OS/toolchain logs, configure/build/CTest logs, CMakeCache and CTest's own log. Recorded compiler: `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`. All three evidence-upload steps succeeded.

Release's `Run Release benchmark and validate evidence` step succeeded. Its downloaded `benchmark.log` records `mixed`, capacity 1000, 1000 commands and one repeat, followed by successful validation. Its separate `report-check.log` records successful validation of one workload/capacity run.

The downloaded Release `summary.json`, raw latency CSV, verification CSV, final snapshots, input/clock hashes and run manifest were locally revalidated using the read-only `validate_run` function. The result contains one latency round and one throughput round; downloaded `report.json` has `validation: passed`. The benchmark manifest's recorded code commit equals the actual PR merge SHA above.

This is functional CI smoke evidence, not a formal performance measurement. No build, benchmark process or new performance measurement was run during this evidence inspection. A successful PR merge-revision check does not replace the later post-merge `main` run.
