"""Recorded command demonstration using two actual matching_client processes."""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=Path)
parser.add_argument("evidence", type=Path)
parser.add_argument("executor", nargs="?", help="Recorded executor; defaults to Codex plus the stage label")
parser.add_argument("--stage", default="M5 T06", help="Evidence stage label (default: M5 T06); does not affect paths")
args = parser.parse_args()
stage = args.stage.strip()
if not stage:
    parser.error("--stage must not be empty")
checkout = args.checkout.resolve()
evidence = args.evidence.resolve()
executor = args.executor if args.executor is not None else f"Codex {stage}"
evidence.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(checkout / "tests"))
from service_harness import ServerRun

os.environ["LLMATCH_SERVICE_ARTIFACTS"] = str(evidence)
commands = []


class Cli:
    def __init__(self, name, port):
        self.name = name
        self.records = []
        self.incoming = queue.Queue()
        self.stderr = (evidence / f"{name}.stderr.log").open("w")
        command = [str(checkout / "build/release/matching_client"), "--port", str(port)]
        commands.append({"process": name, "argv": command})
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, text=True, bufsize=1)

        def read():
            with (evidence / f"{name}.stdout.jsonl").open("w") as output:
                for line in self.process.stdout:
                    output.write(line)
                    output.flush()
                    value = json.loads(line)
                    self.records.append(value)
                    self.incoming.put(value)

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        self.client_id = self.until(lambda value: value["type"] == "welcome")["client"]
        self.until(lambda value: value["type"] == "bbo")

    def until(self, predicate):
        deadline = time.monotonic() + 10
        while True:
            value = self.incoming.get(timeout=max(0, deadline - time.monotonic()))
            if predicate(value):
                return value

    def send(self, line, sequence):
        commands.append({"process": self.name, "stdin": line, "expected_command_seq": sequence})
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        return self.until(lambda value: value.get("kind") == "CommandComplete"
                          and value["command_seq"] == sequence)

    def finish(self):
        self.process.stdin.close()
        assert self.process.wait(timeout=10) == 0, self.name
        self.reader.join(timeout=2)
        assert not self.reader.is_alive()
        self.stderr.close()
        self.process.stdout.close()

    def cleanup(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=2)


clients = []
try:
    with ServerRun(checkout / "build/release/matching_server", "two-real-clients",
                   **{"record-limit": 32, "event-capacity": 1, "command-capacity": 2}) as server:
        maker = Cli("maker", server.port)
        clients.append(maker)
        taker = Cli("taker", server.port)
        clients.append(taker)
        assert maker.client_id != taker.client_id
        assert maker.send("limit 7 101 sell 100 10", 1)["resting_qty"] == 10
        assert taker.send("limit 7 202 buy 90 4", 2)["resting_qty"] == 4
        assert taker.send("market 7 203 buy 3", 3)["filled_qty"] == 3
        assert taker.send("cancel 7 101", 4)["completion"] == "Rejected"
        assert maker.send("cancel 7 101", 5)["cancelled_qty"] == 7
        assert maker.send("market 7 204 sell 4", 6)["filled_qty"] == 4
        assert maker.send("market 7 205 buy 2", 7)["cancelled_qty"] == 2
        for client in clients:
            client.finish()
        report = server.finish()
        assert report["admitted"] == report["completed"] == 7
        assert report["events_published"] == report["events_consumed"]
        assert report["worker_phase"] == "idle"
        trades = [[r for r in client.records if r.get("kind") == "Trade"] for client in clients]
        assert trades[0] == trades[1] and len(trades[0]) == 2
        assert any(r.get("reject_reason") == "NotOwner" for r in taker.records)
        for client, count in ((maker, 4), (taker, 3)):
            assert client.records[-1] == {"type": "client_summary", "submitted": count,
                                          "completed": count, "pending": 0}
            for sequence in (1, 2, 3, 5, 6):
                completes = [i for i, r in enumerate(client.records)
                             if r.get("kind") == "CommandComplete" and r["command_seq"] == sequence]
                if completes:
                    bbo = next(i for i, r in enumerate(client.records)
                               if r["type"] == "bbo" and r["command_seq"] == sequence)
                    assert bbo < completes[0]
        verify_command = [str(checkout / "build/release/verify_service"),
                          "--directory", str(server.directory)]
        commands.append({"process": "reference-verifier", "argv": verify_command})
        result = subprocess.run(verify_command, text=True, capture_output=True, timeout=10)
        (evidence / "verifier.stdout.log").write_text(result.stdout)
        (evidence / "verifier.stderr.log").write_text(result.stderr)
        assert result.returncode == 0, result.stderr
        summary = {"executor": executor, "milestone": stage, "status": "passed",
                   "clients": [maker.client_id, taker.client_id], "commands": 7,
                   "identical_cross_client_trades": 2, "request_id_reused": 7,
                   "bbo_before_complete": True, "reference_verified": True,
                   "server_evidence": str(server.directory)}
        (evidence / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
finally:
    (evidence / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    for client in clients:
        client.cleanup()
