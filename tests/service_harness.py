"""Bounded service subprocess lifecycle shared by real TCP tests."""
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from wire_helpers import WireClient


class ServerRun:
    def __init__(self, server_binary, name, **options):
        self.binary = Path(server_binary).resolve()
        artifacts = Path(os.environ.get("LLMATCH_SERVICE_ARTIFACTS", "service-artifacts")).resolve()
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=name + "-", dir=artifacts))
        self.options = {"port": 0, "record-limit": 10000, "output-dir": self.directory, **options}
        self.clients = []
        self.process = None
        self.report = None

    def __enter__(self):
        command = [str(self.binary)]
        for key, value in self.options.items():
            command += ["--" + key, str(value)]
        (self.directory / "command.json").write_text(json.dumps(command) + "\n")
        self.stderr = (self.directory / "stderr.log").open("wb")
        self.stdout = (self.directory / "stdout.log").open("wb")
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=self.stderr,
                                        cwd=self.directory)
        try:
            deadline = time.monotonic() + 15
            data = bytearray()
            with selectors.DefaultSelector() as ready:
                ready.register(self.process.stdout, selectors.EVENT_READ)
                while b"\n" not in data:
                    events = ready.select(max(0, deadline - time.monotonic()))
                    if not events:
                        raise TimeoutError("server did not emit READY before deadline")
                    chunk = os.read(self.process.stdout.fileno(), 4096)
                    if not chunk:
                        raise AssertionError("server exited before READY")
                    data.extend(chunk)
            self.stdout.write(data)
            self.stdout.flush()
            first = bytes(data).splitlines()[0].decode()
            if not first.startswith("READY "):
                raise AssertionError(f"unexpected server readiness line: {first}")
            self.port = int(first.split()[1])
            return self
        except BaseException:
            self.process.kill()
            remaining, _ = self.process.communicate(timeout=5)
            self.stdout.write(remaining)
            self.stderr.close()
            self.stdout.close()
            print(f"service failure artifacts: {self.directory}", file=sys.stderr)
            raise

    def connect(self, receive_buffer=None):
        client = WireClient(self.port, self.directory / f"client-{len(self.clients) + 1}.jsonl", receive_buffer)
        self.clients.append(client)
        client.welcome()
        return client

    def signal_stop(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)

    def finish(self, expected=0, stop=True):
        if self.report is not None:
            return self.report
        if stop:
            self.signal_stop()
        timeout = float(self.options.get("shutdown-ms", 5000)) / 1000 + 8
        try:
            remaining, _ = self.process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            remaining, _ = self.process.communicate(timeout=5)
            self.stdout.write(remaining)
            self.stdout.flush()
            raise AssertionError("service exceeded bounded shutdown deadline")
        self.stdout.write(remaining)
        self.stdout.flush()
        report = self.directory / "server.json"
        if not report.exists():
            raise AssertionError(f"missing server evidence; exit={self.process.returncode}")
        self.report = json.loads(report.read_text())
        if expected is not None and self.process.returncode != expected:
            raise AssertionError(f"server exit={self.process.returncode}, expected={expected}: {self.report}")
        if self.report["exit_status"] != self.process.returncode:
            raise AssertionError("server report exit status differs from process")
        for name in ("engine.config", "admitted.trace", "final.snapshot", "service_samples.csv"):
            if not (self.directory / name).exists():
                raise AssertionError(f"missing evidence: {name}")
        return self.report

    def __exit__(self, kind, value, traceback):
        failed = kind is not None
        try:
            if self.report is None:
                self.finish(expected=None if failed else 0)
        except BaseException:
            failed = True
            raise
        finally:
            for client in self.clients:
                client.close()
            self.stderr.close()
            self.stdout.close()
            if failed:
                print(f"service failure artifacts: {self.directory}", file=sys.stderr)
            elif os.environ.get("LLMATCH_SERVICE_KEEP_SUCCESS", "1") == "0":
                shutil.rmtree(self.directory)
