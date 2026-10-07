"""In-memory adversarial checks of the production B03.var01 replay gates."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import replay


def reject(label: str, test) -> None:
    try:
        test()
    except (AssertionError, ValueError, KeyError):
        rejected.append(label)
        return
    raise AssertionError(f"mutation escaped: {label}")


def replace_line(log: bytes, old: str, new: str) -> bytes:
    text = log.decode("utf-8-sig")
    assert text.count(old) == 1
    return text.replace(old, new, 1).encode("utf-8")


def swap_lines(log: bytes, first: str, second: str) -> bytes:
    lines = log.decode("utf-8-sig").splitlines(keepends=True)
    a = [i for i, line in enumerate(lines) if first in line]
    b = [i for i, line in enumerate(lines) if second in line]
    assert len(a) == len(b) == 1
    lines[a[0]], lines[b[0]] = lines[b[0]], lines[a[0]]
    return "".join(lines).encode("utf-8")


def mutated_report(report: dict, table: str, row: int, column: str, value: object) -> dict:
    changed = copy.deepcopy(report)
    target = next(t for t in changed["report"]["tables"] if t["name"] == table)
    position = next(i for i, c in enumerate(target["columns"]) if c["name"] == column)
    target["instances"][0]["rows"][row][position] = value
    return changed


def report_gate(report: dict) -> None:
    replay.compare_report(contract, report, expected, records)


if __name__ == "__main__":
    rejected: list[str] = []
    baseline = replay.run()
    assert baseline["report_cells"] == 4044
    contract = json.loads((replay.HERE / "contract.json").read_text(encoding="utf-8"))
    run_dir = Path(contract["parent_runs"][1]["original_directory"])
    source = json.loads((run_dir / "input.json").read_text(encoding="utf-8-sig"))
    export = replay.parse_native((run_dir / "roundtrip-raw.json").read_bytes())
    schedule, _ = replay.check_source_and_roundtrip(contract, source, export)
    log = (run_dir / "model.log").read_bytes()
    records = replay.events(log)
    intervals = replay.check_events(records, schedule)
    expected = replay.report_expected(contract, source, intervals)
    report = replay.parse_native((run_dir / "report-raw.json").read_bytes())

    reject("ready/prepared labels swapped", lambda: report_gate(mutated_report(report, "SystemResults", 15, "NSYRY", 1)))
    reject("prepared wait erased", lambda: report_gate(mutated_report(report, "SystemResults", 15, "NSYMR", 0)))
    reject("fractional hot preparation beyond printed bound", lambda: report_gate(mutated_report(report, "SystemResults", 22, "NSYMP", .334)))
    reject("fractional hot prepared wait beyond printed bound", lambda: report_gate(mutated_report(report, "SystemResults", 30, "NSYMR", .667)))
    reject("interior whole-bin state perturbed", lambda: report_gate(mutated_report(report, "SystemResults", 16, "NSYMO", 1.000000001)))
    reject("source zero perturbed", lambda: report_gate(mutated_report(report, "SystemResults", 20, "NSYUA", 1e-9)))
    reject("mission success count", lambda: report_gate(mutated_report(report, "SystemResults", 22, "NPSUC", 0)))
    reject("summary success fraction", lambda: report_gate(mutated_report(report, "ResultSummary", 0, "MSUF", .9)))
    reject("stock null changed to zero", lambda: report_gate(mutated_report(report, "StockTotalResults", 0, "ROS", 0)))
    reject("stock PNB treated as quantity", lambda: report_gate(mutated_report(report, "StockTotalResults", 0, "PNB", 0)))
    reject("stock invented demand", lambda: report_gate(mutated_report(report, "StockTotalResults", 14, "NDR", 1)))
    reject("physical aircraft identity", lambda: report_gate(mutated_report(report, "SystemResults", 0, "SID", "TEACH-AIR-02")))
    def wrong_instance():
        changed = copy.deepcopy(report)
        next(t for t in changed["report"]["tables"] if t["name"] == "SystemResults")["instances"][0]["instance_name"] += " changed"
        report_gate(changed)
    reject("instance metadata", wrong_instance)
    def wrong_column():
        changed = copy.deepcopy(report)
        next(t for t in changed["report"]["tables"] if t["name"] == "SystemResults")["columns"][5]["datatype"] = "integer"
        report_gate(changed)
    reject("column datatype metadata", wrong_column)

    def event_gate(modified: bytes) -> None:
        replay.check_events(replay.events(modified), schedule)
    reject("cold sequence swapped", lambda: event_gate(swap_lines(log, "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> started")))
    reject("cold resource request changed", lambda: event_gate(replace_line(log, "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources: no resources needed", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources: P-CREW 1")))
    reject("cold mission route changed", lambda: event_gate(replace_line(log, "mission ordered: COLD-FIRST", "mission ordered: HOT-SORTIE")))
    reject("hot prep completion beyond printed bound", lambda: event_gate(replace_line(log, "Time: 11.1667 <TEACH-AIR-01,0> preparation ended", "Time: 11.1677 <TEACH-AIR-01,0> preparation ended")))
    reject("success/return same-time order", lambda: event_gate(swap_lines(log, "<COLD-FIRST,TEACH-UNIT,0,0,0> mission completed", "System arrives <TEACH-AIR-01,0>, mission success")))
    reject("terminal extra mission", lambda: event_gate(log + b"\nTime: 19 <TEACH-UNIT> mission ordered: COLD-FIRST\n"))
    reject("extra physical return outside expected waves", lambda: event_gate(log + b"\nTime: 19 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success\n"))
    reject("extra main preparation task", lambda: event_gate(log + b"\nTime: 19  system preparation task 3 on <TEACH-AIR-01,0> started\n"))
    reject("substituted aircraft in cold allocation", lambda: event_gate(replace_line(log, "<COLD-FIRST,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>", "<COLD-FIRST,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,1>")))

    def wrong_source():
        altered = copy.deepcopy(source)
        table = next(t for t in altered["model"]["tables"] if t["name"] == "OperationProfile")
        position = next(i for i, c in enumerate(table["columns"]) if c["name"] == "SPRID")
        table["instances"][0]["rows"][0][position] = "HOT-SORTIE"
        replay.check_source_and_roundtrip(contract, altered, export)
    reject("source MTID isolation", wrong_source)
    original = run_dir / "model.log"
    pin = copy.deepcopy(contract["parent_runs"][1]["raw"]["model.log"])
    pin["sha256"] = "0" * 64
    reject("raw seal", lambda: replay.check_pin(original, pin))
    inv = run_dir / "invocation.json"
    pin = copy.deepcopy(contract["parent_runs"][1]["invocation"])
    pin["sha256"] = "0" * 64
    reject("invocation seal", lambda: replay.check_pin(inv, pin))
    closure = run_dir / "closure.json"
    pin = copy.deepcopy(contract["parent_runs"][1]["closure"])
    pin["sha256"] = "0" * 64
    reject("closure seal", lambda: replay.check_pin(closure, pin))

    quoted = b'{"x":"literal , ] and , } remain", "y":[1,2,],}'
    assert replay.parse_native(quoted) == {"x": "literal , ] and , } remain", "y": [1, 2]}
    print(json.dumps({"schema": "b03-var01-author-self-check/v1", "baseline_cells": baseline["report_cells"],
                      "semantic_mutations_rejected": len(rejected), "mutation_labels": rejected,
                      "quoted_trailing_comma_parser": "PASS", "new_native_runs": 0}, sort_keys=True, indent=2) + "\n", end="")
