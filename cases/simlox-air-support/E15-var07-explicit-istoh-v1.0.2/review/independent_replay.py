"""Independent standard-library replay of explicit above-nominal ISTOH evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
RUN = CASE / "runs" / "e15-var07-istoh-five-v102-ssh-20261005-01"
PARENT_LOG = PARENT / "runs" / "e15-var07-explicit-three-v101-ssh-20261002-01" / "model.log"
PARENT_REPORT = PARENT / "runs" / "e15-var07-explicit-three-item-v101-ssh-20261002-01" / "item-report-raw.json"
OUT = CASE / "review" / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(value: bool, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path, branch: str) -> dict:
    return {table["name"]: table for table in read(path)[branch]["tables"]}


def cols(table: dict) -> list[str]:
    return [col["name"] for col in table["columns"]]


def rows(table: dict) -> list:
    return table["instances"][0]["rows"]


contract = read(CASE / "contract.json")
closure = read(RUN / "closure.json")
invocation = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
outcome = read(RUN / "outcome.json")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(closure["error"] is None and outcome["error"] is None, "clean closure/outcome")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(len(closure["raw"]) == 13, "thirteen raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"raw exists {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw size {name}")
        check(sha(path) == seal["sha256"], f"raw SHA {name}")
source_paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": PARENT_LOG,
    "parent_report": PARENT_REPORT,
    "selector": PARENT / "runs" / "report-settings" / "item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation")
for name, path in sorted(source_paths.items()):
    check(sha(path) == closure["source_hashes_before"][name], f"source SHA {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0/sshd")
check(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(len(steps) == 4, "four native steps")
for name in ("import", "export", "calc", "report"):
    selected = [step for step in steps if step["name"] == name]
    check(len(selected) == 1 and selected[0]["status"] == "completed" and selected[0]["exit_code"] == 0 and selected[0]["gui_preserved"], f"guarded step {name}")
check(outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 1, 0] and outcome["warning_codes"] == ["108"] and outcome["result"] == "native_run_completed", "native outcome")
calc_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0", calc_log) is not None, "converter summary raw")
check(re.findall(r"\(warning #(\d+)\)", calc_log) == ["108"] and not re.search(r"\(error #\d+\)", calc_log), "converter diagnostics raw")
check((RUN / "model.sxo").stat().st_size > 1000, "valid native result")

parent = tables(PARENT / "native-input-explicit-three.json", "model")
child = tables(RUN / "input.json", "model")
exported = tables(RUN / "roundtrip-raw.json", "model")
check(sha(RUN / "input.json") == sha(CASE / "native-input.json"), "copied input")
check(len(parent) == len(child) == 31 and set(parent) == set(child), "same 31 tables")
for name in sorted(parent):
    if name != "StockAllocation":
        check(child[name] == parent[name], f"unchanged parent table {name}")
stock_names = cols(child["StockAllocation"])
parent_stock = rows(parent["StockAllocation"])
child_stock = rows(child["StockAllocation"])
check(stock_names == cols(parent["StockAllocation"]), "stock column schema")
check(len(parent_stock) == len(child_stock) == 2, "two stock rows")
check(parent_stock[0] == child_stock[0], "unchanged BASE stock row")
check(sum(a != b for pr, cr in zip(parent_stock, child_stock) for a, b in zip(pr, cr)) == 1, "sole source cell")
check(dict(zip(stock_names, parent_stock[1]))["ISTOH"] == 3 and dict(zip(stock_names, child_stock[1]))["ISTOH"] == 5, "depot ISTOH3-to5")
check(dict(zip(stock_names, child_stock[1]))["STSIZ"] == 4 and dict(zip(stock_names, child_stock[1]))["ROSIZ"] == 2, "nominal and batch unchanged")
authored = [name for name, table in child.items() if rows(table)]
check(len(authored) == 21, "21 row-containing authored tables")
for name in authored:
    check(name in exported, f"roundtrip present {name}")
    if name in exported:
        check(cols(child[name]) == cols(exported[name]), f"roundtrip columns {name}")
        check(rows(child[name]) == rows(exported[name]), f"roundtrip rows {name}")

event = (RUN / "model.log").read_text(encoding="utf-8-sig")
for needle in (
    "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
    "Level: 5 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,4>",
    "Level: 1 Items:<TEACH-DU-01,0,5>",
    "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
    "subitem failed: <TEACH-DU-01,0,6>",
    "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,5> from stock",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
    "Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,4>",
    "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,6>",
    "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>",
):
    check(needle in event, f"physical event {needle[:58]}")
check(not re.search(r"reorder task \d+ (?:started|completed)|Delivery with \d+ item\(s\)", event), "no reorder/delivery")
check(event.count("mission starting, duration: 2") == 3 and event.count("mission success:") == 2 and event.count("mission aborted:") == 1, "mission outcomes")
for match in re.finditer(r"Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:([^\n]*)", event):
    ids = re.findall(r"<TEACH-DU-01,0,(\d+)>", match.group(3))
    check(len(ids) == int(match.group(2)) and len(ids) == len(set(ids)), f"physical snapshot {match.group(1)} {match.start()}")

report = tables(RUN / "selected-report-raw.json", "report")
parent_report = tables(PARENT_REPORT, "report")
check(set(report) == set(parent_report) and len(report) == 10, "ten selected tables")
for name in sorted(report):
    check(cols(report[name]) == cols(parent_report[name]), f"report columns {name}")
    check(len(rows(report[name])) == len(rows(parent_report[name])), f"report length {name}")
    if name not in ("ItemResults", "ItemResultsTotal"):
        check(rows(report[name]) == rows(parent_report[name]), f"unchanged parent report {name}")
for name in ("ItemResults", "SystemResults", "StockTotalResults", "MissionResults"):
    check(len(rows(report[name])) == 72, f"72 {name} bins")
item = report["ItemResults"]
names = cols(item)
for i, data in enumerate(rows(item)):
    row = dict(zip(names, data))
    start = i / 2
    check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01", f"selected item bin {i}")
    check(row["STINT"] == start and row["ETINT"] == start + 0.5, f"interval bin {i}")
    check(row["STSZ"] == 4 and row["NBO"] == 0, f"nominal/backorder bin {i}")
    check(row["STOHA"] == (5 if start < 10 else 4), f"on-hand bin {i}")
    check(row["NRO"] == 0, f"no reorder marker bin {i}")
    parent_row = dict(zip(names, rows(parent_report["ItemResults"])[i]))
    for field in names:
        if field != "STOHA" and field != "NRO":
            check(row[field] == parent_row[field], f"other item field {i}/{field}")
total = dict(zip(cols(report["ItemResultsTotal"]), rows(report["ItemResultsTotal"])[0]))
check(abs(total["STOHA"] - (5 * 10 + 4 * 26) / 36) < 1e-5, "time-weighted item on-hand")
check(total["NRO"] == 0, "total reorder zero")
parent_total = dict(zip(cols(parent_report["ItemResultsTotal"]), rows(parent_report["ItemResultsTotal"])[0]))
for name in total:
    if name not in ("STOHA", "NRO"):
        check(total[name] == parent_total[name], f"other item total {name}")
check(rows(item)[-1][names.index("STOHA")] == 4, "terminal depot stock four")

verdict = {
    "schema": "simlox-independent-readonly-review/v1",
    "case": "E15.var07 v1.0.2",
    "run_id": RUN.name,
    "verdict": "PASS_BOUNDED_ABOVE_NOMINAL" if not failures else "EXCLUDE_NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "event_log_sha256": sha(RUN / "model.log"),
    "report_sha256": sha(RUN / "selected-report-raw.json"),
    "scope": "One seed and one depot: explicit opening ISTOH5 exceeds nominal STSIZ4; one h10 issue leaves on-hand4 and no reorder through h36. No general cap or later-demand inference.",
}
OUT.write_text(json.dumps(verdict, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures[:30]))
    raise SystemExit(1)
