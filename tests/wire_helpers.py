"""Independent protocol-v1 layouts and bounded TCP reads for service tests."""
import json
import socket
import struct
import time

HEADER = struct.Struct("!HHI")
EVENT = struct.Struct("!BBQQIQQBBBBqQQQQIIQQQQQ")
BBO = struct.Struct("!BBqQqQQQ")
EVENT_FIELDS = (
    "kind", "command_kind", "command_seq", "event_seq", "client", "request", "order_id",
    "reject_reason", "cancel_reason", "completion", "side", "price", "qty", "arrival_seq",
    "maker_id", "taker_id", "maker_client", "taker_client", "maker_arrival_seq",
    "taker_arrival_seq", "filled_qty", "resting_qty", "cancelled_qty",
)
BBO_FIELDS = ("bid_present", "ask_present", "bid_price", "bid_qty", "ask_price", "ask_qty",
              "command_seq", "as_of_event_seq")
LENGTHS = {1: 4, 5: 130, 6: 50}


def frame(kind, payload):
    return HEADER.pack(1, kind, len(payload)) + payload


def limit(request, order, side, price, qty):
    return frame(2, struct.pack("!QQBqQ", request, order, side, price, qty))


def market(request, order, side, qty):
    return frame(3, struct.pack("!QQBQ", request, order, side, qty))


def cancel(request, order):
    return frame(4, struct.pack("!QQ", request, order))


def business(messages, kind=None):
    return [item for item in messages if item["type"] == 5 and (kind is None or item["kind"] == kind)]


class WireClient:
    def __init__(self, port, log_path, receive_buffer=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if receive_buffer is not None:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer)
        self.socket.connect(("127.0.0.1", port))
        self.log = log_path.open("w")
        self.client_id = None
        self.initial_bbo = None

    def close(self):
        self.socket.close()
        self.log.close()

    def _record(self, direction, data, **extra):
        self.log.write(json.dumps({"direction": direction, "hex": data.hex(), **extra}) + "\n")
        self.log.flush()

    def send(self, data, chunks=None, timeout=5):
        sizes = list(chunks) if chunks is not None else [len(data)]
        if sum(sizes) != len(data):
            raise ValueError("chunk lengths must cover exactly the supplied bytes")
        self._record("send", data, chunks=sizes)
        deadline = time.monotonic() + timeout
        offset = 0
        for size in sizes:
            self.socket.settimeout(max(0.001, deadline - time.monotonic()))
            self.socket.sendall(data[offset:offset + size])
            offset += size

    def _receive_exact(self, count, deadline):
        data = bytearray()
        while len(data) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("TCP frame deadline expired")
            self.socket.settimeout(remaining)
            try:
                chunk = self.socket.recv(count - len(data))
            except ConnectionResetError:
                chunk = b""
            if not chunk:
                if data:
                    raise EOFError(f"truncated response: {len(data)} of {count} bytes")
                return None
            data.extend(chunk)
        return bytes(data)

    def receive(self, deadline=None):
        deadline = deadline if deadline is not None else time.monotonic() + 5
        header = self._receive_exact(8, deadline)
        if header is None:
            return None
        version, kind, length = HEADER.unpack(header)
        if version != 1 or LENGTHS.get(kind) != length:
            raise AssertionError(f"invalid response header {(version, kind, length)}")
        payload = self._receive_exact(length, deadline)
        if payload is None:
            raise EOFError("response ended after its header")
        if kind == 1:
            result = {"type": kind, "client": struct.unpack("!I", payload)[0]}
        else:
            layout, fields = (EVENT, EVENT_FIELDS) if kind == 5 else (BBO, BBO_FIELDS)
            result = {"type": kind, **dict(zip(fields, layout.unpack(payload)))}
        self._record("receive", header + payload, message=result)
        return result

    def welcome(self):
        first, second = self.receive(), self.receive()
        if first is None or first["type"] != 1 or first["client"] == 0:
            raise AssertionError(f"missing Welcome: {first}")
        if second is None or second["type"] != 6:
            raise AssertionError(f"Welcome not followed by BBO: {second}")
        self.client_id = first["client"]
        self.initial_bbo = second
        return second

    def through_complete(self, count=1, timeout=5):
        deadline = time.monotonic() + timeout
        messages = []
        while count:
            message = self.receive(deadline)
            if message is None:
                raise EOFError("connection ended before expected Complete")
            messages.append(message)
            if message["type"] == 5 and message["kind"] == 5:
                count -= 1
        return messages

    def through_bbo(self, command_seq, timeout=5):
        deadline = time.monotonic() + timeout
        messages = []
        while True:
            message = self.receive(deadline)
            if message is None:
                raise EOFError("connection ended before expected BBO")
            messages.append(message)
            if message["type"] == 6 and message["command_seq"] == command_seq:
                return messages

    def through_eof(self, timeout=8):
        deadline = time.monotonic() + timeout
        messages = []
        while True:
            message = self.receive(deadline)
            if message is None:
                return messages
            messages.append(message)
