"""Exercise CLI exit codes and diagnostics through actual subprocesses."""
import pathlib
import subprocess
import sys
import tempfile

replay, shrink, generate = map(pathlib.Path, sys.argv[1:4])
fixtures = pathlib.Path(sys.argv[4])


def invoke(args, expected):
    result = subprocess.run([str(x) for x in args], text=True, capture_output=True)
    assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
    return result


with tempfile.TemporaryDirectory(prefix="llmatch-cli-") as temporary:
    work = pathlib.Path(temporary)
    config = fixtures / "basic.config"
    bad = work / "bad.trace"
    bad.write_text("LLMATCH_TRACE 1\n# physical line numbers count comments\nM 1 1 1 0 -1\n")
    result = invoke([replay, "--engine", "compare", "--config", config, "--input", bad,
                     "--output-dir", work / "bad"], 1)
    assert f"{bad}:3:" in result.stderr, result.stderr
    for engine in ("baseline", "reference", "compare"):
        invoke([replay, "--engine", engine, "--config", config,
                "--input", fixtures / "basic.trace", "--output-dir", work / engine], 0)
    for filename in ("events.txt", "snapshot.txt"):
        assert (work / "baseline" / filename).read_bytes() == (work / "reference" / filename).read_bytes()
        assert (work / "baseline" / filename).read_bytes() == (work / "compare" / filename).read_bytes()
    invoke([replay, "--engine", "compare", "--config", config,
            "--input", fixtures / "rejections.trace", "--output-dir", work / "rejects"], 0)
    result = invoke([shrink, "--config", config, "--input", fixtures / "basic.trace",
                     "--output", work / "nothing.trace"], 1)
    assert "no differential failure" in result.stderr, result.stderr
    for name in ("first.trace", "second.trace"):
        invoke([generate, "--config", config, "--seed", "817", "--count", "200",
                "--output", work / name], 0)
    assert (work / "first.trace").read_bytes() == (work / "second.trace").read_bytes()
    assert "seed 817" in (work / "first.trace.meta").read_text()
    invoke([replay, "--engine", "compare", "--config", config, "--input", work / "first.trace",
            "--output-dir", work / "generated"], 0)
print("CLI diagnostics, deterministic generation, replay modes and exit codes passed")
