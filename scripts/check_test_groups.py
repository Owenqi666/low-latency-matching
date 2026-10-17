#!/usr/bin/env python3
"""Check CTest discovery and, after execution, its JUnit evidence.

Save discovery with ``ctest --preset PRESET --show-only=json-v1``. Run this
script before CTest, then again with --junit after CTest. The second check
requires every discovered test to have run successfully, without skips.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


DEFAULT_GROUPS = ("core", "pausable", "protocol", "concurrency", "service", "client", "loadgen", "itch")
GROUPS = (*DEFAULT_GROUPS, "benchmark")
CORE_PREFIXES = (
    "Contract.", "EngineTest.", "OrderBookTest.", "Reference.",
    "DifferentialTest.", "TraceIO.", "replay_", "regression_", "cli_contract",
)


def in_group(test, group):
    name = test["name"]
    if group in ("protocol", "concurrency", "service", "benchmark", "itch"):
        properties = {item["name"]: item["value"] for item in test.get("properties", [])}
        return group in properties.get("LABELS", []) or (group == "benchmark" and name == "benchmark_pipeline")
    if group == "core":
        return name.startswith(CORE_PREFIXES)
    if group == "pausable":
        return name.startswith("PausableEngineTest.")
    return name == {"client": "client_cli", "loadgen": "loadgen_contract"}[group]


def check(discovery, junit, required):
    data = json.loads(discovery.read_text())
    if data.get("kind") != "ctestInfo" or data.get("version", {}).get("major") != 1:
        raise ValueError("expected CTest --show-only=json-v1 output")
    tests = data["tests"]
    names = [test["name"] for test in tests]
    errors = []
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate discovered tests: {duplicates}")
    if not tests:
        errors.append("CTest discovered no tests")
    for test in tests:
        properties = {item["name"]: item["value"] for item in test.get("properties", [])}
        if properties.get("DISABLED") is True:
            errors.append(f"disabled discovered test: {test['name']}")
        if not test.get("command"):
            errors.append(f"discovered test has no executable command: {test['name']}")

    members = {
        group: {test["name"] for test in tests if in_group(test, group)}
        for group in required
    }
    groups = {group: {"discovered": len(found)} for group, found in members.items()}
    for group, found in members.items():
        if not found:
            errors.append(f"required group is empty: {group}")

    result = {"phase": "execution" if junit else "discovery", "discovered": len(tests),
              "groups": groups, "errors": errors}
    if junit:
        root = ET.parse(junit).getroot()
        cases = list(root.iter("testcase"))
        case_names = [case.attrib["name"] for case in cases]
        duplicates = sorted(name for name, count in Counter(case_names).items() if count > 1)
        if duplicates:
            errors.append(f"duplicate JUnit results: {duplicates}")
        missing = sorted(set(names) - set(case_names))
        extra = sorted(set(case_names) - set(names))
        if missing:
            errors.append(f"discovered tests missing from JUnit: {missing}")
        if extra:
            errors.append(f"JUnit contains undiscovered tests: {extra}")
        passed = set()
        for case in cases:
            if (case.get("status") != "run" or case.find("skipped") is not None
                    or case.find("failure") is not None or case.find("error") is not None):
                errors.append(f"test did not pass without skipping: {case.attrib['name']}")
            else:
                passed.add(case.attrib["name"])
        for suite in root.iter("testsuite"):
            for count in ("failures", "errors", "disabled", "skipped"):
                if int(suite.get(count, "0")) != 0:
                    errors.append(f"JUnit suite reports {count}={suite.get(count)}")
        for group, found in members.items():
            groups[group]["passed"] = len(found & passed)
        result["junit_results"] = len(cases)
        result["passed"] = len(passed)
    result["valid"] = not errors
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--require", action="append", choices=GROUPS,
                        help="required nonempty group; repeat as needed (default: core, service and ITCH groups)")
    args = parser.parse_args()
    try:
        result = check(args.discovery, args.junit, args.require or DEFAULT_GROUPS)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        print(f"test group evidence invalid: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
