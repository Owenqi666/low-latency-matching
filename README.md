# llmatch — M1 matching core

A single-threaded, in-memory C++20 matching core under development. The original
planning documents remain local; public contracts will live in `docs/semantics.md`.
Limit orders, market IOC, owner-checked cancellation and an independent reference
model are implemented and tested. Replay tools and benchmark delivery are in
progress; no performance claims are published yet.

Requires a C++20 compiler, CMake >= 3.24, Ninja, and network access for the first
GoogleTest 1.17.0 download. GoogleTest is a test-only dependency, configured using
the [official CMake integration](https://google.github.io/googletest/quickstart-cmake.html).

```sh
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure --no-tests=error
```

Replace `debug` with `release` or `asan-ubsan` for the other configurations.
The sanitizer flags apply to project code, not just the test entry point.

Implementation and acceptance progress: [docs/progress.md](docs/progress.md).
