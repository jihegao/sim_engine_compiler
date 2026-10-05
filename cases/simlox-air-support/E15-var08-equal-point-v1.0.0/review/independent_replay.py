"""Read-only independent replay of the excluded E15.var08 equality diagnostic."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "E15-var07-explicit-istoh-v1.0.1"
RUN = CASE / "runs/e15-var08-equal-point-v100-ssh-20261005-01"
OUT = CASE / "review/independent-verdict.json"
checks = 0
failures: list[str] = []


def test(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    return {table["name"]: table for table in read(path)["model"]["tables"]}


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


contract, closure = read(CASE / "contract.json"), read(RUN / "closure.json")
invocation, outcome, steps = (read(RUN / x) for x in ("invocation.json", "outcome.json", "steps.json"))
test(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
test(closure["error"] == outcome["error"] == "frozen equal-point event gate failed", "frozen rejection")
test(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
test(len(closure["raw"]) == 11, "eleven diagnostic raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    test(path.is_file(), f"raw exists {name}")
    if path.is_file():
        test(path.stat().st_size == seal["bytes"], f"raw size {name}")
        test(digest(path) == seal["sha256"], f"raw digest {name}")

parent_run = PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01"
parent_report = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01"
sources = {
    "contract": CASE / "contract.json", "input": CASE / "native-input.json",
    "builder": CASE / "build.py", "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": parent_run / "model.log",
    "parent_report": parent_report / "item-report-raw.json",
    "selector": PARENT / "runs/report-settings/item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
test(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation")
for key, path in sorted(sources.items()):
    test(digest(path) == closure["source_hashes_before"][key], f"source digest {key}")
for key, field in (("input", "input_sha256"), ("builder", "builder_sha256"), ("roundtrip_checker", "roundtrip_checker_sha256"), ("selector", "selector_sha256"), ("selector_builder", "selector_builder_sha256"), ("manual", "manual_pdf_sha256"), ("exe", "simlox_exe_sha256")):
    test(contract["source"][field] == closure["source_hashes_before"][key], f"contract source pin {key}")
for key, field in (("parent_input", "input_sha256"), ("parent_signoff", "signoff_sha256"), ("parent_index", "evidence_index_sha256"), ("parent_event", "event_log_sha256"), ("parent_report", "selected_report_sha256")):
    test(contract["accepted_parent"][field] == closure["source_hashes_before"][key], f"contract parent pin {key}")
for directory, expected in ((parent_run, 12), (parent_report, 2)):
    sealed = read(directory / "closure.json")["raw"]
    test(len(sealed) == expected, f"parent raw count {directory.name}")
    for name, seal in sorted(sealed.items()):
        path = directory / name
        test(path.is_file(), f"parent raw exists {directory.name}/{name}")
        if path.is_file():
            test(path.stat().st_size == seal["bytes"], f"parent raw size {directory.name}/{name}")
            test(digest(path) == seal["sha256"], f"parent raw digest {directory.name}/{name}")

test(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0/sshd")
test(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
test(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "GUI identity")
test([step["name"] for step in steps] == ["import", "export", "calc"], "three stages; report absent")
for step in steps:
    test(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"guarded {step['name']}")
test(not (RUN / "selected-report-raw.json").exists() and not (RUN / "report-export.log").exists(), "no selected report after failed gate")
test(outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 1, 0] and outcome["warning_codes"] == ["108"], "diagnostic conversion outcome")
calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
test("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc, "raw converter counts")
test(re.findall(r"\(warning #(\d+)\)", calc) == ["108"] and not re.search(r"\(error #\d+\)", calc), "raw warning set")
test((RUN / "model.sxo").stat().st_size > 1000, "usable calculated SXO despite exclusion")

parent, child, exported = (tables(path) for path in (PARENT / "native-input-explicit-three.json", RUN / "input.json", RUN / "roundtrip-raw.json"))
test(digest(RUN / "input.json") == digest(CASE / "native-input.json"), "copied input")
test(len(parent) == len(child) == 31 and set(parent) == set(child), "31-table topology")
for name in sorted(parent):
    if name != "StockAllocation":
        test(parent[name] == child[name], f"unchanged table {name}")
columns = [col["name"] for col in child["StockAllocation"]["columns"]]
original, modified = rows(parent["StockAllocation"]), rows(child["StockAllocation"])
test(sum(a != b for x, y in zip(original, modified) for a, b in zip(x, y)) == 1, "one source cell")
test(dict(zip(columns, original[1]))["ISTOH"] == 3 and dict(zip(columns, modified[1]))["ISTOH"] == 2, "depot ISTOH3-to2")
test(dict(zip(columns, modified[1]))["STSIZ"] == 4 and dict(zip(columns, modified[1]))["ROSIZ"] == 2, "reorder point two")
authored = [name for name, table in child.items() if rows(table)]
test(len(authored) == 21, "21 row-containing tables")
for name in authored:
    test(name in exported, f"export table {name}")
    if name in exported:
        test(child[name]["columns"] == exported[name]["columns"], f"typed columns {name}")
        test(rows(child[name]) == rows(exported[name]), f"rows {name}")

event = (RUN / "model.log").read_text(encoding="utf-8-sig")
for needle in (
    "Level: 2 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>",
    "Level: 1 Items:<TEACH-DU-01,0,2>",
    "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:",
    "subitem failed: <TEACH-DU-01,0,3>",
    "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,2> from stock",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
    "Level: 1 Items:<TEACH-DU-01,0,1>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
    "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
    "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 3 item(s) arrives",
    "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,3>",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>",
):
    test(needle in event, f"observed event {needle[:63]}")
test(not re.search(r"(?m)^Time: 0 .*reorder task", event), "no h0 reorder")
test(len(re.findall(r"reorder task \d+ started", event)) == 1 and len(re.findall(r"Delivery with \d+ item\(s\)", event)) == 1, "one h10 order/h11 delivery")
test(event.count("mission starting, duration: 2") == 3 and event.count("mission success:") == 2 and event.count("mission aborted:") == 1, "mission counts")
stock = list(re.finditer(r"Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:([^\n]*)", event))
observed = [(m.group(1), int(m.group(2)), re.findall(r"<TEACH-DU-01,0,(\d+)>", m.group(3))) for m in stock]
test(observed == [
    ("DEPOT-01", 2, ["0", "1"]), ("BASE-01", 1, ["2"]),
    ("BASE-01", 0, []), ("DEPOT-01", 1, ["1"]),
    ("DEPOT-01", 2, ["1", "4"]), ("DEPOT-01", 3, ["1", "4", "5"]),
    ("DEPOT-01", 4, ["1", "4", "5", "6"]), ("BASE-01", 1, ["0"]),
], "complete physical stock snapshots")
for i, (_, level, ids) in enumerate(observed):
    test(level == len(ids) == len(set(ids)), f"stock conservation snapshot {i}")

verdict = {
    "schema": "simlox-independent-diagnostic-review/v1",
    "case": "E15.var08 v1.0.0",
    "run_id": RUN.name,
    "decision": "GO_EXCLUDE_FROZEN_H0_HYPOTHESIS" if not failures else "NO_GO_EVIDENCE_REPLAY",
    "accepted_case": False,
    "checks_passed": checks - len(failures), "checks_total": checks,
    "failures": failures,
    "closure_sha256": digest(RUN / "closure.json"),
    "event_log_sha256": digest(RUN / "model.log"),
    "scope": "At ISTOH=point2, no initial reorder is logged; h10 issue leaves one on hand and starts a one-hour three-item reorder, delivered h11. Frozen h0 order/two-item gate failed. No selected report was exported; no positive E15.var08 acceptance.",
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{verdict['decision']} {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures[:30]))
    raise SystemExit(1)
