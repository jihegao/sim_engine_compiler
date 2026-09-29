"""Mutate reclosed copies of final raw runs to exercise behavior assertions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

import validate


def reseal(run: Path, name: str) -> None:
    closure = validate.load(run / "closure.json")
    path = run / name
    closure["raw"][name] = {"bytes": path.stat().st_size, "sha256": validate.sha(path)}
    (run / "closure.json").write_text(json.dumps(closure, indent=2) + "\n", encoding="utf-8")


def run_control(source: Path, mutate, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="c04-negative-") as temp:
        copy_path = Path(temp) / source.name
        shutil.copytree(source, copy_path)
        mutate(copy_path)
        result = validate.check(copy_path)
        if result["passed"] or not any(expected in difference for difference in result["differences"]):
            raise AssertionError({"expected": expected, "differences": result["differences"]})


def remove_wait_stop(run: Path) -> None:
    path = run / "model.log"
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    found = [i for i, line in enumerate(lines) if "resource waiting stopped" in line]
    if len(found) != 2:
        raise AssertionError("unexpected native wait-stop control source")
    del lines[found[0]]
    path.write_text("".join(lines), encoding="utf-8")
    reseal(run, "model.log")


def phantom_occupancy(run: Path) -> None:
    path = run / "report-raw.json"
    report = validate.load(path)
    table = next(item for item in report["report"]["tables"] if item["name"] == "ResourceResults")
    columns = [column["name"] for column in table["columns"]]
    table["instances"][0]["rows"][15][columns.index("NRUM")] = 0
    path.write_text(json.dumps(report) + "\n", encoding="utf-8")
    reseal(run, "report-raw.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=Path(__file__).resolve().parent / "runs")
    args = parser.parse_args()
    zero = args.run_root / "c04-v100-crew-zero-ssh-20260929-02"
    before = args.run_root / "c04-v100-crew-before-ssh-20260929-02"
    if not validate.check(zero)["passed"] or not validate.check(before)["passed"]:
        raise AssertionError("source final runs must pass before negative controls")
    run_control(zero, remove_wait_stop, "wait stops")
    run_control(before, phantom_occupancy, "resource ledger interval 15")
    print("2 reclosed C04 negative controls rejected as expected")


if __name__ == "__main__":
    main()
