"""Independent standard-library replay of the sealed I07.var04 native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "i07-var04-old-cycle-v100-ssh-20261005-01"
SOURCE_PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.0"
ACCEPTED = ROOT / "E15-var01-time-based-cycle-v1.0.1"
REPORT_PARENT = ACCEPTED / "runs" / "e15-var01-timecycle-report-v101-ssh-20261005-01" / "selected-report-raw.json"
LOG_PARENT = SOURCE_PARENT / "runs" / "e15-var01-timecycle-v100-ssh-20261005-01" / "model.log"
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


def rows(table: dict) -> list:
    return table["instances"][0]["rows"]


def cols(table: dict) -> list[str]:
    return [col["name"] for col in table["columns"]]


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
    "parent_input": SOURCE_PARENT / "native-input.json",
    "parent_signoff": ACCEPTED / "cli-scope-signoff-2026-10-05.md",
    "parent_index": ACCEPTED / "evidence-index.json",
    "parent_event": LOG_PARENT,
    "parent_report": REPORT_PARENT,
    "selector": ROOT / "E15-var07-explicit-istoh-v1.0.1" / "runs" / "report-settings" / "item-position-results.sxs",
    "selector_builder": ROOT / "E15-var07-explicit-istoh-v1.0.1" / "make_report_settings.py",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation")
for name, path in sorted(source_paths.items()):
    check(sha(path) == closure["source_hashes_before"][name], f"source SHA {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0/sshd")
check(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "native mutex")
check(len(steps) == 4, "four native steps")
for name in ("import", "export", "calc", "report"):
    selected = [step for step in steps if step["name"] == name]
    check(len(selected) == 1 and selected[0]["status"] == "completed" and selected[0]["exit_code"] == 0 and selected[0]["gui_preserved"], f"guarded step {name}")
check(outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 2, 0] and outcome["warning_codes"] == ["108", "376"] and outcome["result"] == "native_run_completed", "native outcome")
log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", log) is not None, "converter summary raw")
check(re.findall(r"\(warning #(\d+)\)", log) == ["108", "376"] and not re.search(r"\(error #\d+\)", log), "converter diagnostics raw")
check("Form: StockAllocation\nrec 2: (warning #376) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01" in log.replace("\r\n", "\n"), "row-specific #376")
check((RUN / "model.sxo").stat().st_size > 1000, "valid nonempty SXO")

parent = tables(SOURCE_PARENT / "native-input.json", "model")
child = tables(RUN / "input.json", "model")
exported = tables(RUN / "roundtrip-raw.json", "model")
check(sha(RUN / "input.json") == sha(CASE / "native-input.json"), "copied child input")
check(len(parent) == 31 and len(child) == 32 and set(child) == set(parent) | {"ChangesItemReorder"}, "31 parent plus one change table")
for name in sorted(parent):
    check(child[name] == parent[name], f"unchanged parent table {name}")
new = child["ChangesItemReorder"]
check(cols(new) == ["IID", "STID", "TIMEC", "LEADT", "DISCF", "LEADTD", "ROINT", "NOTE"], "change schema")
check(rows(new) == [["TEACH-DU-01", "DEPOT-01", 5.0, 1.0, None, None, 8.0, None]], "sole h5 interval change")
authored = [name for name, table in child.items() if rows(table)]
check(len(authored) == 22, "22 row-containing authored tables")
for name in authored:
    check(name in exported, f"roundtrip present {name}")
    if name in exported:
        check(cols(child[name]) == cols(exported[name]), f"roundtrip columns {name}")
        check(rows(child[name]) == rows(exported[name]), f"roundtrip rows {name}")

native_log = (RUN / "model.log").read_bytes()
check(native_log == LOG_PARENT.read_bytes(), "full native event log equals accepted E15 parent")
events = native_log.decode("utf-8-sig")
for needle in (
    "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
    "Level: 4 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>",
    "Time: 16 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
    "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
    "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives",
    "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>",
    "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
):
    check(needle in events, f"physical event {needle[:54]}")
check(len(re.findall(r"reorder task \d+ started", events)) == 1 and len(re.findall(r"reorder task \d+ completed", events)) == 1, "one first-cycle order")
check(not any(5 <= float(m.group(1)) < 16 for m in re.finditer(r"Time: ([0-9.]+) .*?reorder task \d+ started", events)), "no early order at h5/h8")
check(events.count("mission starting, duration: 2") == 3 and events.count("mission success:") == 2 and events.count("mission aborted:") == 1, "three mission outcomes")

report = tables(RUN / "selected-report-raw.json", "report")
parent_report = tables(REPORT_PARENT, "report")
check((RUN / "selected-report-raw.json").read_bytes() == REPORT_PARENT.read_bytes(), "full selected-report byte parity")
check(set(report) == set(parent_report) and len(report) == 10, "ten report tables")
for name in sorted(report):
    check(cols(report[name]) == cols(parent_report[name]), f"report columns {name}")
    check(rows(report[name]) == rows(parent_report[name]), f"report data {name}")
for name in ("ItemResults", "SystemResults", "StockTotalResults", "MissionResults"):
    check(len(rows(report[name])) == 72, f"72 {name} bins")
item = report["ItemResults"]
names = cols(item)
for i, values in enumerate(rows(item)):
    row = dict(zip(names, values))
    start = i / 2
    check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01", f"depot selector bin {i}")
    check(row["STINT"] == start and row["ETINT"] == start + 0.5, f"half-hour interval {i}")
    check(row["STSZ"] == 4 and row["NBO"] == 0, f"nominal/backorder bin {i}")
    check(row["STOHA"] == (4 if start < 10 or start >= 17 else 3), f"physical on-hand bin {i}")
    check(row["NRO"] == (1 if start == 16 else 0), f"reorder marker bin {i}")
summary = dict(zip(cols(report["ResultSummary"]), rows(report["ResultSummary"])[0]))
check(summary["NREP"] == 1 and summary["MSTF"] == 1 and abs(summary["MSUF"] - 2 / 3) < 1e-6, "summary missions")
check(rows(report["ItemResults"])[-1][names.index("STOHA")] == 4, "terminal depot stock four")

verdict = {
    "schema": "simlox-independent-readonly-review/v1",
    "case": "I07.var04 v1.0.0",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED_FIRST_CYCLE" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "event_log_sha256": sha(RUN / "model.log"),
    "report_sha256": sha(RUN / "selected-report-raw.json"),
    "scope": "With an h5 authored ROINT16-to8 change, this fixed-seed run retains its first h16 order and h17 delivery; the later eight-hour interval is not observed.",
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures))
    raise SystemExit(1)
