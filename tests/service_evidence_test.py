"""Verify real service artifacts and reject corrupted or unsuccessful evidence.

Usage: service_evidence_test.py MATCHING_SERVER VERIFY_SERVICE REPLAY [unittest options]
"""
from contextlib import contextmanager
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from service_harness import ServerRun
from wire_helpers import EVENT_FIELDS, business, cancel, limit, market

SERVER, VERIFIER, REPLAY = (Path(value).resolve() for value in sys.argv[1:4])
del sys.argv[1:4]


def verify(directory):
    result = subprocess.run([str(VERIFIER), "--directory", str(directory)],
                            text=True, capture_output=True, timeout=10)
    (directory / "verifier.stdout.log").write_text(result.stdout)
    (directory / "verifier.stderr.log").write_text(result.stderr)
    return result


def edit_samples(directory, edit):
    path = directory / "service_samples.csv"
    with path.open(newline="") as source:
        rows = list(csv.reader(source))
    edit(rows)
    with path.open("w", newline="") as output:
        csv.writer(output, lineterminator="\n").writerows(rows)


def edit_report(directory, **values):
    path = directory / "server.json"
    report = json.loads(path.read_text())
    report.update(values)
    path.write_text(json.dumps(report) + "\n")


def change_digest(directory):
    def change(rows):
        rows[2][10] = str(int(rows[2][10]) ^ 1)
    edit_samples(directory, change)


def swap_input(directory):
    path = directory / "admitted.trace"
    lines = path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n")


def remove_rejected_suffix(directory):
    # The last request is rejected, so this trimmed prefix has the same final
    # book and valid per-command digests. Only server counts expose the omission.
    path = directory / "admitted.trace"
    path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
    edit_samples(directory, lambda rows: rows.pop())


def erase_recorded_work(directory):
    (directory / "admitted.trace").write_text("LLMATCH_TRACE 1\n")
    def keep_header(rows):
        del rows[1:]
    edit_samples(directory, keep_header)
    (directory / "final.snapshot").write_text("BOOK 1\n")


class ServiceEvidenceTest(unittest.TestCase):
    @contextmanager
    def valid_evidence(self):
        with ServerRun(SERVER, "evidence-valid", **{"record-limit": 32, "event-capacity": 1}) as server:
            maker = server.connect()
            maker.send(limit(11, 1, 1, 100, 5))
            maker.through_complete()
            taker = server.connect()
            taker.send(market(22, 2, 0, 2))
            taker.through_complete()
            maker.through_bbo(2)
            maker.send(cancel(11, 1))
            maker.through_complete()
            taker.send(market(22, 3, 0, 4) + limit(22, 4, 0, 90, 1) + market(0, 5, 0, 1))
            taker.through_complete(3)
            report = server.finish()
            self.assertEqual((report["admitted"], report["completed"]), (6, 6))
            result = verify(server.directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            verification = json.loads((server.directory / "verification.json").read_text())
            self.assertEqual(verification["result"], "passed")
            self.assertEqual((verification["commands"], verification["trades"], verification["rejected"]),
                             (6, 1, 1))
            yield server.directory

    def assert_rejected_without_stale_success(self, directory):
        result = verify(directory)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((directory / "verification.json").exists(),
                         "failed validation left an old passed report")

    def test_real_reference_result_and_corrupted_evidence(self):
        mutations = {
            "changed-digest": change_digest,
            "missing-sample": lambda d: edit_samples(d, lambda rows: rows.pop(2)),
            "extra-sample": lambda d: edit_samples(d, lambda rows: rows.append(rows[-1].copy())),
            "wrong-final-book": lambda d: (d / "final.snapshot").write_text("BOOK 1\n"),
            "changed-input-order": swap_input,
            "consistent-prefix-omission": remove_rejected_suffix,
            "empty-records-with-live-counts": erase_recorded_work,
            "failed-run": lambda d: edit_report(d, exit_status=1, failure="shutdown deadline exhausted"),
            "wrong-consumed-count": lambda d: edit_report(d, events_consumed=0),
            "wrong-published-count": lambda d: edit_report(d, events_published=0),
            "missing-server-report": lambda d: (d / "server.json").unlink(),
        }
        with self.valid_evidence() as valid:
            for name, mutate in mutations.items():
                with self.subTest(mutation=name):
                    directory = Path(tempfile.mkdtemp(prefix=f"evidence-{name}-", dir=valid.parent))
                    shutil.copytree(valid, directory, dirs_exist_ok=True)
                    # Copy a genuine passed report, then mutate its source evidence.
                    self.assertTrue((directory / "verification.json").exists())
                    mutate(directory)
                    try:
                        self.assert_rejected_without_stale_success(directory)
                    except BaseException:
                        print(f"service evidence failure artifacts: {directory}", file=sys.stderr)
                        raise
                    if os.environ.get("LLMATCH_SERVICE_KEEP_SUCCESS", "1") == "0":
                        shutil.rmtree(directory)

    def test_full_network_events_routing_and_bbo_match_independent_reference(self):
        commands = [
            (0, limit(11, 10, 0, 90, 5)),
            (1, limit(11, 20, 1, 100, 7)),
            (0, limit(11, 11, 0, 80, 9)),
            (1, limit(11, 21, 1, 100, 3)),
            (2, market(11, 30, 0, 8)),
            (0, cancel(11, 20)),
            (0, cancel(11, 21)),
            (1, limit(11, 20, 1, 105, 2)),
            (1, market(11, 31, 0, 1)),
            (1, cancel(11, 21)),
            (0, cancel(11, 10)),
            (2, market(11, 32, 1, 9)),
            (1, cancel(11, 20)),
            (2, market(11, 33, 0, 1)),
            (0, limit(0, 34, 255, -1, 0)),
            (0, limit(11, 10, 0, 88, 2)),
            (0, market(11, 10, 1, 1)),
            (2, limit(11, 40, 1, 80, 1)),
        ]
        with ServerRun(SERVER, "evidence-full-network", **{
                "record-limit": 32, "command-capacity": 1, "event-capacity": 1}) as server:
            clients = [server.connect(), server.connect()]
            actual = {client.client_id: [client.initial_bbo] for client in clients}
            joined_after = {client.client_id: 0 for client in clients}
            for number, (client_index, command) in enumerate(commands, 1):
                client = clients[client_index]
                client.send(command)
                actual[client.client_id].extend(client.through_complete())
                if number == 4:
                    client = server.connect()
                    clients.append(client)
                    joined_after[client.client_id] = number
                    actual[client.client_id] = [client.initial_bbo]
            report = server.finish()
            for client in clients:
                actual[client.client_id].extend(client.through_eof())
            self.assertEqual((report["admitted"], report["completed"]), (18, 18))
            self.assertEqual(report["missing_business_recipients"], 0)
            self.assertEqual(report["discarded_business_frames"], 0)
            trace_lines = (server.directory / "admitted.trace").read_text().splitlines()
            self.assertEqual(len(trace_lines), 19)
            quote_keys = ("bid_present", "ask_present", "bid_price", "bid_qty", "ask_price", "ask_qty")
            previous = dict.fromkeys(quote_keys, 0)
            latest_bbo = {"type": 6, **previous, "command_seq": 0, "as_of_event_seq": 0}
            expected = {client: [latest_bbo.copy()] if after == 0 else []
                        for client, after in joined_after.items()}

            def route(event, number):
                recipients = {event["maker_client"], event["taker_client"]} if event["kind"] == 2 else {event["client"]}
                for recipient in recipients:
                    if recipient in expected and joined_after[recipient] < number:
                        expected[recipient].append(event)

            # ReferenceEngine is exercised through the existing public replay CLI.
            # Prefix snapshots independently derive final BBO changes; no production
            # core, queue, routing implementation or recorded digest supplies them.
            for number in range(1, 19):
                input_path = server.directory / f"reference-prefix-{number}.trace"
                input_path.write_text("\n".join(trace_lines[:number + 1]) + "\n")
                output_path = server.directory / f"reference-{number}"
                result = subprocess.run([str(REPLAY), "--engine", "reference", "--config",
                    str(server.directory / "engine.config"), "--input", str(input_path),
                    "--output-dir", str(output_path)], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                reference_events = []
                event_lines = (output_path / "events.txt").read_text().splitlines()
                self.assertEqual(event_lines[0], "LLMATCH_EVENTS 1")
                for line in event_lines[1:]:
                    values = line.split()
                    self.assertEqual(values[0], "E")
                    self.assertEqual(len(values) - 1, len(EVENT_FIELDS))
                    event = {"type": 5, **dict(zip(EVENT_FIELDS, map(int, values[1:])))}
                    if event["command_seq"] == number:
                        reference_events.append(event)
                self.assertEqual(reference_events[-1]["kind"], 5)
                complete = reference_events[-1]
                for event in reference_events[:-1]:
                    route(event, number)
                quote = dict.fromkeys(quote_keys, 0)
                for line in (output_path / "snapshot.txt").read_text().splitlines():
                    values = line.split()
                    if values[0] == "B" and not quote["bid_present"]:
                        quote.update(bid_present=1, bid_price=int(values[1]), bid_qty=int(values[2]))
                    elif values[0] == "A" and not quote["ask_present"]:
                        quote.update(ask_present=1, ask_price=int(values[1]), ask_qty=int(values[2]))
                if quote != previous:
                    latest_bbo = {"type": 6, **quote, "command_seq": number,
                                  "as_of_event_seq": complete["event_seq"] - 1}
                    for recipient in expected:
                        if joined_after[recipient] < number:
                            expected[recipient].append(latest_bbo.copy())
                    previous = quote
                route(complete, number)
                for recipient, after in joined_after.items():
                    if after == number:
                        expected[recipient].append(latest_bbo.copy())
            (server.directory / "network-expected.json").write_text(json.dumps(expected, indent=2) + "\n")
            (server.directory / "network-actual.json").write_text(json.dumps(actual, indent=2) + "\n")
            self.assertEqual(actual, expected)
            result = verify(server.directory)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabled_recording_cannot_claim_zero_command_validation(self):
        with ServerRun(SERVER, "evidence-recording-disabled", **{"record-limit": 0}) as server:
            client = server.connect()
            client.send(market(1, 1, 0, 1))
            client.through_complete()
            report = server.finish()
            self.assertEqual((report["admitted"], report["completed"]), (1, 1))
            self.assertEqual((server.directory / "admitted.trace").read_text(), "LLMATCH_TRACE 1\n")
            self.assert_rejected_without_stale_success(server.directory)

    def test_real_shutdown_deadline_failure_cannot_get_passed_report(self):
        with ServerRun(SERVER, "evidence-deadline-failed", **{
                "record-limit": 2000, "socket-send-buffer": 1024, "send-limit": 1048576,
                "shutdown-ms": 100, "event-capacity": 4}) as server:
            slow = server.connect(receive_buffer=1024)
            slow.send(limit(1, 1, 1, 100, 1010))
            slow.through_complete()
            healthy = server.connect()
            for request in range(1, 1001):
                healthy.send(market(request, request + 100, 0, 1))
                self.assertEqual(business(healthy.through_complete(), 5)[0]["filled_qty"], 1)
            report = server.finish(expected=1)
            self.assertEqual(report["failure"], "shutdown deadline exhausted")
            self.assertEqual((report["admitted"], report["completed"]), (1001, 1001))
            self.assertEqual(report["current_admission"], 0)
            self.assertEqual(report["worker_phase"], "idle")
            self.assertFalse(report["worker_aborted"])
            self.assertGreater(report["discarded_business_frames"], 0)
            self.assert_rejected_without_stale_success(server.directory)


if __name__ == "__main__":
    unittest.main()
