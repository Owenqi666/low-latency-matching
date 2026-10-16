"""Real TCP service checks. Every run retains evidence in service-artifacts/.

Usage: python3 service_test.py /absolute/path/matching_server [unittest options]
LLMATCH_SERVICE_ARTIFACTS overrides the output root; LLMATCH_SERVICE_KEEP_SUCCESS=0
removes successful cases. Unexpected failures always retain their run directories.
"""
from pathlib import Path
import socket
import struct
import sys
import unittest

from service_harness import ServerRun
from wire_helpers import HEADER, business, cancel, frame, limit, market

SERVER = Path(sys.argv.pop(1)).resolve()


class ServiceTest(unittest.TestCase):
    def assert_drained(self, report, admitted):
        self.assertEqual(report["admitted"], admitted)
        self.assertEqual(report["completed"], admitted)
        self.assertEqual(report["uncompleted"], 0)
        self.assertEqual(report["current_admission"], 0)
        self.assertEqual(report["worker_phase"], "idle")
        self.assertFalse(report["worker_aborted"])
        self.assertEqual(report["events_consumed"], report["events_published"])
        self.assertEqual(report["bbo_consumed"], report["bbo_published"])
        self.assertEqual(report["failure"], "")

    def assert_bbo_before_complete(self, messages, command_seq):
        positions = [(i, m) for i, m in enumerate(messages) if m.get("command_seq") == command_seq]
        quotes = [(i, m) for i, m in positions if m["type"] == 6]
        completes = [(i, m) for i, m in positions if m["type"] == 5 and m["kind"] == 5]
        self.assertEqual(len(quotes), 1)
        self.assertEqual(len(completes), 1)
        self.assertLess(quotes[0][0], completes[0][0])
        self.assertEqual(quotes[0][1]["as_of_event_seq"], completes[0][1]["event_seq"] - 1)
        return quotes[0][1]

    def test_fragmented_and_coalesced_requests(self):
        with ServerRun(SERVER, "fragment-coalesce", **{"command-capacity": 1, "event-capacity": 1}) as server:
            client = server.connect()
            self.assertEqual(client.initial_bbo["command_seq"], 0)
            raw = limit(11, 101, 0, 100, 7)
            client.send(raw, chunks=[1] * len(raw))
            first = client.through_complete()
            self.assertEqual([e["kind"] for e in business(first)], [0, 3, 5])
            self.assertEqual(self.assert_bbo_before_complete(first, 1)["bid_qty"], 7)
            client.send(cancel(12, 101) + market(13, 102, 0, 4))
            rest = client.through_complete(2)
            self.assertEqual([e["kind"] for e in business(rest)], [0, 4, 5, 0, 4, 5])
            self.assertEqual([e["command_seq"] for e in business(rest, 5)], [2, 3])
            self.assertEqual(business(rest, 5)[-1]["cancelled_qty"], 4)
            self.assert_bbo_before_complete(rest, 2)
            # Cross both the 16-frame pump budget and the 4 KiB receive buffer.
            client.send(b"".join(market(42, 1000 + i, 0, 1) for i in range(129)))
            burst = client.through_complete(129)
            self.assertEqual([e["command_seq"] for e in business(burst, 5)], list(range(4, 133)))
            self.assertEqual([e["order_id"] for e in business(burst, 5)], list(range(1000, 1129)))
            self.assertTrue(all(e["request"] == 42 for e in business(burst)))
            self.assert_drained(server.finish(), 132)

    def test_protocol_errors_and_truncated_eof_do_not_consume_sequences(self):
        with ServerRun(SERVER, "protocol-errors") as server:
            invalid = [HEADER.pack(2, 4, 16), HEADER.pack(1, 99, 0), HEADER.pack(1, 4, 17),
                       HEADER.pack(1, 4, 0xFFFFFFFF), frame(1, struct.pack("!I", 123))]
            for raw in invalid:
                client = server.connect()
                client.send(raw)
                self.assertIsNone(client.receive())
            for raw in (b"\x00\x01\x00", cancel(1, 1)[:-1]):
                client = server.connect()
                client.send(raw)
                client.socket.shutdown(socket.SHUT_WR)
                self.assertIsNone(client.receive())
            valid = server.connect()
            valid.send(limit(0, 0, 255, -1, 0) + market(1, 1, 255, 0))
            responses = valid.through_complete(2)
            self.assertEqual([e["reject_reason"] for e in business(responses, 1)], [2, 4])
            self.assertEqual([e["command_seq"] for e in business(responses, 5)], [1, 2])
            report = server.finish()
            self.assert_drained(report, 2)
            self.assertEqual(report["close_reasons"]["protocol_error"], len(invalid))
            self.assertEqual(report["close_reasons"]["truncated_frame"], 2)

    def test_cross_client_routing_owner_checks_repeated_requests_and_self_trade(self):
        with ServerRun(SERVER, "routing") as server:
            maker = server.connect()
            maker.send(limit(1, 10, 1, 100, 5))
            maker.through_complete()
            taker = server.connect()
            self.assertNotEqual(maker.client_id, taker.client_id)
            self.assertEqual(taker.initial_bbo["ask_qty"], 5)
            self.assertEqual(taker.initial_bbo["command_seq"], 1)
            taker.send(market(9, 20, 0, 2))
            taking = taker.through_complete()
            making = maker.through_bbo(2)
            self.assertEqual(business(taking, 2), business(making, 2))
            self.assertEqual(len(business(taking, 2)), 1)
            trade = business(taking, 2)[0]
            self.assertEqual((trade["maker_client"], trade["taker_client"], trade["client"], trade["request"]),
                             (maker.client_id, taker.client_id, taker.client_id, 9))
            self.assertEqual(self.assert_bbo_before_complete(taking, 2)["ask_qty"], 3)
            taker.send(cancel(9, 10))
            rejected = taker.through_complete()
            self.assertEqual([e["kind"] for e in business(rejected)], [1, 5])
            self.assertEqual(business(rejected, 1)[0]["reject_reason"], 9)
            self.assertFalse(any(m["type"] == 6 for m in rejected))
            maker.send(cancel(1, 10))
            removed = maker.through_complete()
            self.assertEqual([e["kind"] for e in business(removed)], [0, 4, 5])
            maker.send(limit(17, 30, 1, 101, 2) + cancel(17, 30) +
                       limit(17, 30, 1, 101, 2) + market(17, 31, 0, 1))
            repeated = maker.through_complete(4)
            self.assertEqual([e["command_seq"] for e in business(repeated, 5)], [5, 6, 7, 8])
            self.assertEqual(len(business(repeated, 0)), 4)
            self.assertEqual(len(business(repeated, 2)), 1)
            self.assertTrue(all(e["request"] == 17 for e in business(repeated)))
            self.assert_drained(server.finish(), 8)

    def test_disconnect_retains_orders_and_reconnect_gets_new_identity(self):
        with ServerRun(SERVER, "disconnect-retained") as server:
            old = server.connect()
            old.send(limit(1, 10, 1, 100, 3))
            old.through_complete()
            old.socket.close()
            new = server.connect()
            self.assertGreater(new.client_id, old.client_id)
            self.assertEqual(new.initial_bbo["ask_qty"], 3)
            new.send(cancel(1, 10))
            self.assertEqual(business(new.through_complete(), 1)[0]["reject_reason"], 9)
            new.send(market(2, 20, 0, 3))
            frames = new.through_complete()
            self.assertEqual(business(frames, 2)[0]["maker_client"], old.client_id)
            self.assertEqual(business(frames, 5)[0]["filled_qty"], 3)
            report = server.finish()
            self.assert_drained(report, 3)
            self.assertGreater(report["missing_business_recipients"] + report["discarded_business_frames"], 0)
            self.assertEqual((server.directory / "final.snapshot").read_text(), "BOOK 1\n")

    def test_event_capacities_one_two_four_sweep_64_makers(self):
        for capacity in (1, 2, 4):
            with self.subTest(event_capacity=capacity):
                with ServerRun(SERVER, f"sweep-{capacity}", capacity=128,
                               **{"command-capacity": 1, "event-capacity": capacity}) as server:
                    client = server.connect()
                    for order in range(1, 65):
                        client.send(limit(order, order, 1, 100 + order, 1))
                        client.through_complete()
                    client.send(market(65, 100, 0, 70))
                    messages = client.through_complete()
                    trades = business(messages, 2)
                    self.assertEqual(len(trades), 64)
                    self.assertEqual([e["maker_id"] for e in trades], list(range(1, 65)))
                    self.assertEqual([e["maker_arrival_seq"] for e in trades], list(range(1, 65)))
                    self.assertEqual([e["price"] for e in trades], list(range(101, 165)))
                    self.assertTrue(all(e["qty"] == 1 for e in trades))
                    self.assertEqual([e["event_seq"] for e in business(messages)], list(range(193, 260)))
                    complete = business(messages, 5)[0]
                    self.assertEqual((complete["filled_qty"], complete["cancelled_qty"]), (64, 6))
                    quote = self.assert_bbo_before_complete(messages, 65)
                    self.assertEqual((quote["bid_present"], quote["ask_present"], quote["as_of_event_seq"]),
                                     (0, 0, 258))
                    report = server.finish()
                    self.assert_drained(report, 65)
                    self.assertLessEqual(report["event_high_water"], capacity)

    def test_shutdown_after_accepted_drains_admitted_prefix(self):
        with ServerRun(SERVER, "shutdown-prefix", **{"command-capacity": 1, "event-capacity": 1}) as server:
            client = server.connect()
            client.send(b"".join(market(i, i, 0, 1) for i in range(1, 129)))
            first = client.receive()
            self.assertEqual((first["type"], first["kind"]), (5, 0))
            server.signal_stop()
            messages = [first, *client.through_eof()]
            report = server.finish(stop=False)
            self.assert_drained(report, report["admitted"])
            self.assertGreaterEqual(report["admitted"], 1)
            self.assertLessEqual(report["admitted"], 128)
            self.assertEqual(len(business(messages, 5)), report["admitted"])
            self.assertEqual([e["command_seq"] for e in business(messages, 5)],
                             list(range(1, report["admitted"] + 1)))
            self.assertEqual(report["discarded_business_frames"], 0)

    def exercise_slow_peer(self, server, count=1000):
        slow = server.connect(receive_buffer=1024)
        slow.send(limit(1, 1, 1, 100, count + 10))
        slow.through_complete()
        healthy = server.connect()
        for request in range(1, count + 1):
            healthy.send(market(request, request + 100, 0, 1))
            messages = healthy.through_complete()
            self.assertEqual(business(messages, 5)[0]["filled_qty"], 1)
        return slow, healthy

    def test_slow_client_is_closed_while_healthy_client_keeps_completing(self):
        with ServerRun(SERVER, "slow-client", **{"socket-send-buffer": 1024, "send-limit": 8192,
                                         "event-capacity": 4, "command-capacity": 4}) as server:
            self.exercise_slow_peer(server)
            report = server.finish()
            self.assert_drained(report, 1001)
            self.assertGreaterEqual(report["close_reasons"]["slow_client"], 1)
            self.assertGreater(report["missing_business_recipients"] + report["discarded_business_frames"], 0)
            self.assertLessEqual(report["send_high_water"], 8192)

    def test_blocked_socket_shutdown_deadline_is_failure_with_delivery_evidence(self):
        with ServerRun(SERVER, "shutdown-deadline", **{"socket-send-buffer": 1024, "send-limit": 1048576,
                                               "shutdown-ms": 100, "event-capacity": 4}) as server:
            self.exercise_slow_peer(server)
            report = server.finish(expected=1)
            self.assertEqual(report["failure"], "shutdown deadline exhausted")
            self.assertEqual(report["admitted"], 1001)
            self.assertEqual(report["completed"], 1001)
            self.assertEqual(report["uncompleted"], 0)
            self.assertEqual(report["current_admission"], 0)
            self.assertEqual(report["worker_phase"], "idle")
            self.assertFalse(report["worker_aborted"])
            self.assertEqual(report["close_reasons"]["slow_client"], 0)
            self.assertGreater(report["discarded_business_frames"], 0)

    def test_record_capacity_exhaustion_stops_without_unbounded_records(self):
        with ServerRun(SERVER, "record-capacity", **{"record-limit": 2, "event-capacity": 1}) as server:
            client = server.connect()
            client.send(market(1, 1, 0, 1) + market(2, 2, 0, 1) + market(3, 3, 0, 1))
            messages = client.through_eof()
            report = server.finish(expected=1, stop=False)
            self.assertEqual(report["failure"], "experiment record capacity exhausted")
            self.assertEqual(report["admitted"], 2)
            self.assertEqual(report["completed"], 2)
            self.assertEqual(len(business(messages, 5)), 2)


if __name__ == "__main__":
    unittest.main()
