"""Fail closed when pytest collection and JUnit execution evidence diverge."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def _collected_cases(path: Path) -> Counter[tuple[str, str]]:
    cases: Counter[tuple[str, str]] = Counter()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("tests/") or "::" not in line:
            continue
        parts = line.split("::")
        file_path = parts[0]
        if not file_path.endswith(".py") or len(parts) < 2:
            continue
        module = file_path[:-3].replace("/", ".")
        classname = ".".join((module, *parts[1:-1]))
        cases[(classname, parts[-1])] += 1
    if not cases:
        raise ValueError(f"no pytest node IDs found in {path}")
    return cases


def _junit_cases(
    path: Path,
) -> tuple[
    Counter[tuple[str, str]], dict[tuple[str, str], list[str]], dict[str, int]
]:
    root = ET.parse(path).getroot()
    cases: Counter[tuple[str, str]] = Counter()
    statuses: dict[tuple[str, str], list[str]] = {}
    counts = {"recorded": 0, "passed": 0, "skipped": 0, "failures": 0, "errors": 0}
    for testcase in root.iter("testcase"):
        key = (testcase.get("classname", ""), testcase.get("name", ""))
        cases[key] += 1
        counts["recorded"] += 1
        if testcase.find("error") is not None:
            status = "error"
            counts["errors"] += 1
        elif testcase.find("failure") is not None:
            status = "failed"
            counts["failures"] += 1
        elif testcase.find("skipped") is not None:
            status = "skipped"
            counts["skipped"] += 1
        else:
            status = "passed"
            counts["passed"] += 1
        statuses.setdefault(key, []).append(status)
    if not cases:
        raise ValueError(f"no testcase records found in {path}")
    counts["executed"] = counts["passed"] + counts["failures"] + counts["errors"]
    return cases, statuses, counts


def verify(
    collection_path: Path,
    junit_path: Path,
    required_modules: list[str],
) -> dict[str, object]:
    collected = _collected_cases(collection_path)
    executed, statuses, counts = _junit_cases(junit_path)
    diagnostics: list[str] = []

    if counts["failures"] or counts["errors"]:
        diagnostics.append(
            "JUnit contains nonpassing execution results: "
            f"failures={counts['failures']}, errors={counts['errors']}"
        )

    missing_from_execution = collected - executed
    unexpected_in_execution = executed - collected
    if missing_from_execution:
        diagnostics.append(
            "collected tests missing from JUnit: "
            + repr(sorted(missing_from_execution.elements())[:10])
        )
    if unexpected_in_execution:
        diagnostics.append(
            "JUnit tests absent from collection: "
            + repr(sorted(unexpected_in_execution.elements())[:10])
        )

    required_counts: dict[str, int] = {}
    for module_path in required_modules:
        normalized = module_path.removesuffix(".py").replace("/", ".")
        module_cases = [
            key
            for key in executed.elements()
            if key[0] == normalized or key[0].startswith(normalized + ".")
        ]
        required_counts[module_path] = len(module_cases)
        if not module_cases:
            diagnostics.append(f"required module did not execute: {module_path}")
        nonpassing = [
            (key, status)
            for key in module_cases
            for status in statuses[key]
            if status != "passed"
        ]
        if nonpassing:
            diagnostics.append(
                f"required module has nonpassing tests: {module_path}: {nonpassing[:10]!r}"
            )

    counts["collected"] = sum(collected.values())
    evidence: dict[str, object] = {
        "schema_version": "pytest-execution-evidence/v1",
        **counts,
        "required_modules": required_counts,
        "status": "passed" if not diagnostics else "failed",
        "diagnostics": diagnostics,
    }
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--require-module", action="append", default=[])
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = verify(args.collection, args.junit, args.require_module)
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"identity test evidence is invalid: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
