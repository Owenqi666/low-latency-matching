"""Bounded open-loop loadgen checks using a real server and independent wire peers."""
import csv
import json
import pathlib
import selectors
import signal
import socket
import struct
import subprocess
import sys
import threading

LOADGEN = pathlib.Path(sys.argv[1]).resolve()
SERVER = pathlib.Path(sys.argv[2]).resolve()
WORK = pathlib.Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else LOADGEN.parent / "loadgen-test-evidence"
WORK.mkdir(parents=True, exist_ok=True)
HEADER = struct.Struct("!HHI")
EVENT = struct.Struct("!BBQQIQQBBBBqQQQQIIQQQQQ")


def write_inputs(directory, setup, commands, offsets):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "setup.trace").write_text("LLMATCH_TRACE 1\n" + "".join(line + "\n" for line in setup))
    (directory / "input.trace").write_text("LLMATCH_TRACE 1\n" + "".join(line + "\n" for line in commands))
    (directory / "schedule.txt").write_text("".join(str(value) + "\n" for value in offsets))


def run(directory, port, connections=1, expected=0, extra=()):
    result = subprocess.run([
        str(LOADGEN), "--port", str(port), "--connections", str(connections),
        "--setup", str(directory / "setup.trace"), "--input", str(directory / "input.trace"),
        "--schedule", str(directory / "schedule.txt"), "--output-dir", str(directory / "client"),
        "--drain-ms", "1000", *extra], text=True, capture_output=True, timeout=10)
    (directory / "loadgen.stdout.log").write_text(result.stdout)
    (directory / "loadgen.stderr.log").write_text(result.stderr)
    assert result.returncode == expected, (result.returncode, result.stdout, result.stderr, directory)
    report = json.loads((directory / "client/client.json").read_text())
    rows = list(csv.DictReader((directory / "client/client_samples.csv").open()))
    setup = list(csv.DictReader((directory / "client/setup_samples.csv").open()))
    for counts, samples in ((report, rows), (report["setup"], setup)):
        assert counts["planned"] == len(samples)
        assert counts["planned"] == counts["not_started"] + counts["started"]
        assert counts["started"] == counts["completed"] + counts["failed"] + counts["unfinished"]
        assert counts["completed"] == counts["accepted"] + counts["rejected"]
        assert counts["not_started"] == sum(not row["first_attempt_ns"] for row in samples)
        assert counts["completed"] == sum(row["outcome"] == "completed" for row in samples)
        assert counts["failed"] == sum(row["outcome"] == "failed" for row in samples)
        assert counts["unfinished"] == sum(row["outcome"] == "unfinished" for row in samples)
        for index, row in enumerate(samples):
            assert int(row["idx"]) == index
            if row["complete_ns"]:
                assert int(row["rtt_ns"]) == int(row["complete_ns"]) - int(row["first_attempt_ns"])
                assert int(row["rtt_ns"]) >= 0
            else:
                assert row["rtt_ns"] == ""
            if row["scheduled_ns"] and row["first_attempt_ns"]:
                assert int(row["send_lag_ns"]) == int(row["first_attempt_ns"]) - int(row["scheduled_ns"])
                assert int(row["send_lag_ns"]) >= 0
    offsets = [int(value) for value in (directory / "schedule.txt").read_text().splitlines()]
    for row, offset in zip(rows, offsets):
        if report["measurement_start_ns"]:
            assert int(row["scheduled_ns"]) == report["measurement_start_ns"] + offset
        else:
            assert row["scheduled_ns"] == ""
    assert all(row["scheduled_ns"] == "" for row in setup)
    assert report["exit_status"] == expected
    assert report["inflight_high_water"] <= report["max_inflight"]
    assert all(value["send_high_water"] <= report["max_send_bytes"] for value in report["logical_to_actual"])
    assert report["clock_probe"]["samples"] == 10000
    assert report["tcp_nodelay"] is True
    return report, rows, setup


class RealServer:
    def __init__(self, directory):
        self.directory = directory
        self.process = subprocess.Popen([
            str(SERVER), "--port", "0", "--record-limit", "2000", "--output-dir", str(directory / "server")],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                assert selector.select(timeout=8), "server did not signal readiness"
                ready = self.process.stdout.readline()
            assert ready.startswith("READY "), ready
            self.port = int(ready.split()[1])
            (directory / "server.stdout.log").write_text(ready)
        except BaseException:
            self.process.kill()
            self.process.wait(timeout=2)
            raise

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGTERM)
            stdout, stderr = self.process.communicate(timeout=8)
            with (self.directory / "server.stdout.log").open("a") as output:
                output.write(stdout)
            (self.directory / "server.stderr.log").write_text(stderr)
            assert self.process.returncode == 0, stderr
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=2)


success = WORK / "real"
write_inputs(success, ["L 1 1 1 1 100 10", "L 2 1 2 0 90 5"],
             ["M 2 2 3 0 7", "C 1 2 1", "L 1 3 4 0 95 2", "M 1 4 5 1 2", "C 2 3 2"],
             [0, 20000000, 40000000, 60000000, 80000000])
server = RealServer(success)
try:
    report, samples, setup = run(success, server.port, connections=2)
finally:
    server.close()
assert report["completed"] == 5 and report["setup"]["completed"] == 2
mapping = {item["logical"]: item["actual"] for item in report["logical_to_actual"]}
assert len(set(mapping.values())) == 2 and all(mapping.values())
service = {row["command_seq"]: row for row in csv.DictReader((success / "server/service_samples.csv").open())}
assert len(service) == 7
for sample in samples + setup:
    actual = service[sample["command_seq"]]
    assert int(sample["actual"]) == mapping[int(sample["logical"])]
    for client_field, service_field in (("actual", "client"), ("request", "request"),
                                      ("events", "events"), ("trades", "trades"),
                                      ("checksum", "checksum"), ("completion_status", "status")):
        assert sample[client_field] == actual[service_field], (sample, actual, client_field)

for name, extra, reason in (("inflight", ("--max-inflight", "1"), "max_inflight"),
                            ("send_limit", ("--max-send-bytes", "8"), "send_limit")):
    directory = WORK / name
    write_inputs(directory, [], [f"C 1 {i + 1} {i + 1}" for i in range(8)], [0] * 8)
    server = RealServer(directory)
    try:
        report, samples, _ = run(directory, server.port, expected=1, extra=extra)
    finally:
        server.close()
    assert report["not_started"] > 0
    assert all(row["failure"] == reason for row in samples if row["outcome"] == "not_started")
    if name == "inflight":
        assert report["started"] == report["completed"] == 1 and report["not_started"] == 7
    else:
        assert report["started"] == 0 and report["not_started"] == 8


def wire(kind, payload):
    return HEADER.pack(1, kind, len(payload)) + payload


def acknowledgement():
    return wire(5, EVENT.pack(0, 2, 1, 1, 17, 1, 1, 0, 0, 0, *([0] * 13)))


def exact(connection, count):
    result = bytearray()
    while len(result) < count:
        piece = connection.recv(count - len(result))
        assert piece, "loadgen closed before its request"
        result.extend(piece)
    return bytes(result)


def mock_case(name, response):
    directory = WORK / name
    write_inputs(directory, [], ["C 1 1 1"], [0])
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(8)

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    connection.sendall(wire(1, struct.pack("!I", 17)))
                    version, kind, length = HEADER.unpack(exact(connection, 8))
                    assert (version, kind, length) == (1, 4, 16)
                    assert exact(connection, length) == struct.pack("!QQ", 1, 1)
                    response(connection)
            except BaseException as error:
                errors.append(error)

        peer = threading.Thread(target=serve, daemon=True)
        peer.start()
        report, samples, _ = run(directory, listener.getsockname()[1], expected=1, extra=("--drain-ms", "500"))
        peer.join(timeout=6)
        assert not peer.is_alive() and not errors, errors
    return report, samples


def stall(connection):
    connection.sendall(acknowledgement())
    assert connection.recv(1) == b""


report, samples = mock_case("deadline", stall)
assert report["unfinished"] == 1 and samples[0]["failure"] == "deadline"
assert samples[0]["events"] == "1" and samples[0]["complete_ns"] == ""

report, samples = mock_case("disconnect", lambda connection: connection.sendall(acknowledgement()))
assert report["failed"] == 1 and samples[0]["failure"] == "disconnected"

report, samples = mock_case("truncated", lambda connection: connection.sendall(acknowledgement()[:11]))
assert report["failed"] == 1 and samples[0]["failure"] == "protocol"

invalid = WORK / "invalid"
write_inputs(invalid, ["C 1 1 1"], ["C 1 1 2"], [0])
result = subprocess.run([str(LOADGEN), "--setup", str(invalid / "setup.trace"),
                         "--input", str(invalid / "input.trace"), "--schedule", str(invalid / "schedule.txt"),
                         "--output-dir", str(invalid / "client")], text=True, capture_output=True, timeout=3)
assert result.returncode == 1 and "unique per logical client" in result.stderr
(invalid / "stderr.log").write_text(result.stderr)

print("loadgen: real-service event hashes, open-loop limits, count conservation, setup separation, disconnect and deadline evidence passed")
