"""Exercise matching_client against an independent, bounded TCP wire peer."""
import atexit
import json
import pathlib
import queue
import socket
import struct
import subprocess
import sys
import threading
import time

CLIENT = pathlib.Path(sys.argv[1]).resolve()
HEADER = struct.Struct("!HHI")
EVENT = struct.Struct("!BBQQIQQBBBBqQQQQIIQQQQQ")
BBO = struct.Struct("!BBqQqQQQ")
CLIENT_ID = 17


def frame(kind, payload):
    return HEADER.pack(1, kind, len(payload)) + payload


def event(kind, command_kind=0, cseq=1, eseq=1, request=7, order=1,
          client=CLIENT_ID, reject=0, completion=0, **fields):
    names = ("side", "price", "qty", "arrival_seq", "maker_id", "taker_id",
             "maker_client", "taker_client", "maker_arrival_seq", "taker_arrival_seq",
             "filled_qty", "resting_qty", "cancelled_qty")
    values = [fields.get(name, 0) for name in names]
    return frame(5, EVENT.pack(kind, command_kind, cseq, eseq, client, request,
                               order, reject, 0, completion, *values))


def exact(connection, count):
    result = bytearray()
    while len(result) < count:
        part = connection.recv(count - len(result))
        assert part, ("unexpected client EOF", count, len(result))
        result.extend(part)
    return bytes(result)


def request(connection):
    version, kind, length = HEADER.unpack(exact(connection, HEADER.size))
    assert version == 1 and (kind, length) in ((2, 33), (3, 25), (4, 16))
    return kind, exact(connection, length)


class Peer:
    def __init__(self, handler):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(10)
        self.errors = []
        self.records = []
        self.lines = queue.Queue()

        def serve():
            try:
                connection, _ = self.listener.accept()
                with connection:
                    connection.settimeout(9)
                    # Byte writes cover fragmented handshakes without sleep-based
                    # timing; codec unit tests cover every possible read boundary.
                    welcome = frame(1, struct.pack("!I", CLIENT_ID))
                    for byte in welcome:
                        connection.sendall(bytes([byte]))
                    connection.sendall(frame(6, BBO.pack(0, 0, 0, 0, 0, 0, 0, 0)))
                    handler(connection)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.listener.close()

        self.server = threading.Thread(target=serve, daemon=True)
        self.server.start()
        self.process = subprocess.Popen(
            [str(CLIENT), "--port", str(self.listener.getsockname()[1])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        atexit.register(self.close)

        def read_output():
            for line in self.process.stdout:
                self.lines.put(line)

        self.reader = threading.Thread(target=read_output, daemon=True)
        self.reader.start()
        self.until(lambda value: value.get("type") == "bbo")

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()
        self.listener.close()

    def write(self, text, eof=False):
        self.process.stdin.write(text)
        self.process.stdin.flush()
        if eof:
            self.process.stdin.close()

    def until(self, predicate):
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            record = json.loads(self.lines.get(timeout=max(0.01, deadline - time.monotonic())))
            self.records.append(record)
            if predicate(record):
                return record
        raise AssertionError("expected output did not arrive")

    def finish(self, expected):
        try:
            code = self.process.wait(timeout=10)
            self.reader.join(timeout=1)
            self.server.join(timeout=1)
            stderr = self.process.stderr.read()
            while not self.lines.empty():
                self.records.append(json.loads(self.lines.get_nowait()))
            assert code == expected, (code, expected, self.records, stderr)
            assert not self.server.is_alive(), "wire peer did not finish"
            assert not self.errors, self.errors
            summary = self.records[-1]
            assert summary["type"] == "client_summary", self.records
            return summary, stderr
        finally:
            self.close()


def idle_maker(connection):
    kind, body = request(connection)
    assert kind == 2 and struct.unpack("!QQBqQ", body) == (7, 1, 1, 100, 5)
    connection.sendall(event(0) + event(3, eseq=2, side=1, price=100, qty=5)
                       + frame(6, BBO.pack(0, 1, 0, 0, 100, 5, 1, 2))
                       + event(5, eseq=3, completion=1, resting_qty=5))
    # The client has no stdin activity here and must still read a maker fill.
    connection.sendall(event(2, cseq=2, eseq=5, client=88, request=7, order=99,
                             price=100, qty=2, maker_id=1, taker_id=99,
                             maker_client=CLIENT_ID, taker_client=88))
    assert connection.recv(1) == b""


peer = Peer(idle_maker)
peer.write("limit 7 1 sell 100 5\n")
trade = peer.until(lambda value: value.get("kind") == "Trade")
assert trade["maker_client"] == CLIENT_ID and trade["taker_client"] == 88
assert peer.process.poll() is None, "client stopped while stdin remained open"
peer.write("quit\n")
summary, _ = peer.finish(0)
assert summary == {"type": "client_summary", "submitted": 1, "completed": 1, "pending": 0}


def duplicates(connection):
    expected = ((2, struct.pack("!QQBqQ", 7, 1, 0, 100, 3)),
                (3, struct.pack("!QQBQ", 7, 2, 1, 1)),
                (4, struct.pack("!QQ", 7, 1)))
    for value in expected:
        assert request(connection) == value
    connection.sendall(event(2, cseq=9, eseq=20, client=88, request=7, order=99,
                             maker_client=CLIENT_ID, taker_client=88))
    for index, order in enumerate((1, 2, 1)):
        connection.sendall(event(0, command_kind=index, cseq=10 + index,
                                 eseq=21 + 2 * index, order=order)
                           + event(5, command_kind=index, cseq=10 + index,
                                   eseq=22 + 2 * index, order=order, completion=1))
    assert connection.recv(1) == b""


peer = Peer(duplicates)
peer.write("limit 7 1 buy 100 3\nmarket 7 2 sell 1\ncancel 7 1\n", eof=True)
summary, _ = peer.finish(0)
assert summary["submitted"] == summary["completed"] == 3 and summary["pending"] == 0


def rejection(connection):
    assert request(connection) == (2, struct.pack("!QQBqQ", 0, 0, 0, -1, 0))
    connection.sendall(event(1, request=0, order=0, reject=2)
                       + event(5, eseq=2, request=0, order=0, completion=2))
    assert connection.recv(1) == b""


peer = Peer(rejection)
# Invalid syntax is diagnosed; the following representable business error still
# reaches the wire. EOF's final line need not have a terminating newline.
peer.write("limit 1 1 wrong 100 2\nlimit 0 0 buy -1 0", eof=True)
summary, stderr = peer.finish(0)
assert "side must be buy or sell" in stderr
assert summary["completed"] == 1
assert any(value.get("reject_reason") == "InvalidRequestId" for value in peer.records)


def disconnect(connection):
    request(connection)
    connection.sendall(event(0))


peer = Peer(disconnect)
peer.write("limit 7 1 buy 100 1\n", eof=True)
summary, stderr = peer.finish(1)
assert summary["pending"] == 1 and summary["completed"] == 0
assert "server disconnected" in stderr


def truncated(connection):
    request(connection)
    connection.sendall(event(0)[:11])


peer = Peer(truncated)
peer.write("limit 7 1 buy 100 1\n", eof=True)
_, stderr = peer.finish(1)
assert "truncated server frame" in stderr


def bounded_stall(connection):
    for _ in range(1024):
        assert request(connection)[0] == 4
    # Request 1025 and EOF remain behind paused stdin. The progress deadline must
    # still close the client; this also proves the pending bound is enforced.
    assert connection.recv(1) == b""


peer = Peer(bounded_stall)
peer.write("cancel 7 1\n" * 1025, eof=True)
summary, stderr = peer.finish(1)
assert summary["submitted"] == summary["pending"] == 1024 and summary["completed"] == 0
assert "Complete deadline exceeded" in stderr


def overlong(connection):
    assert connection.recv(1) == b""


peer = Peer(overlong)
peer.write("x" * 4096 + "\n", eof=True)
summary, stderr = peer.finish(1)
assert summary["submitted"] == 0 and "maximum line 4096" in stderr

for arguments in (("--port", "0"), ("--port", "65536"), ("--port", "-1"), ("--unknown", "x")):
    result = subprocess.run([str(CLIENT), *arguments], capture_output=True, text=True, timeout=2)
    assert result.returncode == 1, (arguments, result)

print("client CLI: idle maker reception, duplicate IDs, EOF drain, errors, bounded input and completion deadline passed")
