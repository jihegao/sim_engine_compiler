"""Independent, standard-library-only read of the sealed I07.var02 diagnostic."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "i07-var02-rosiz-v100-ssh-20261005-01"
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
PARENT_LOG = PARENT / "runs" / "e15-var07-explicit-three-v101-ssh-20261002-01" / "model.log"
PARENT_REPORT = PARENT / "runs" / "e15-var07-explicit-three-item-v101-ssh-20261002-01" / "item-report-raw.json"
OUT = CASE / "review" / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path, branch: str) -> dict:
    return {t["name"]: t for t in load(path)[branch]["tables"]}


def rows(table: dict) -> list:
    return table["instances"][0]["rows"]


def cols(table: dict) -> list[str]:
    return [c["name"] for c in table["columns"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "closure/outcome clean")
check(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(len(closure["raw"]) == 24, "24 raw entries")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"raw exists: {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw size: {name}")
        check(digest(path) == seal["sha256"], f"raw hash: {name}")

source_paths = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": PARENT / "make_report_settings.py",
    "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector": PARENT / "runs" / "report-settings" / "item-position-results.sxs",
    "control": CASE / "control-input.json",
    "change": CASE / "change-input.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "runner": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source before/after")
check(invocation["source_hashes_before"] == closure["source_hashes_before"], "invocation source binding")
for key, path in sorted(source_paths.items()):
    check(digest(path) == closure["source_hashes_before"][key], f"source hash: {key}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session 0")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check(invocation["gui"]["start_utc"] == "2026-09-28T10:09:56.8261381Z", "GUI start identity")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(len(steps) == 8, "eight native steps")
for arm in ("control", "change"):
    for verb in ("import", "export", "calc", "report"):
        selected = [s for s in steps if s["name"] == f"{arm}_{verb}"]
        check(len(selected) == 1 and selected[0]["status"] == "completed" and selected[0]["exit_code"] == 0 and selected[0]["gui_preserved"], f"guarded {arm} {verb}")
    check(outcome["arms"][arm] == "completed", f"{arm} completed")
    check(outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"], f"{arm} diagnostics")
    check((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} valid result")

parent_input = tables(PARENT / "native-input-explicit-three.json", "model")
inputs = {arm: tables(RUN / f"{arm}-input.json", "model") for arm in ("control", "change")}
check(len(parent_input) == 31 and all(len(t) == 32 for t in inputs.values()), "31/32 table structure")
check(set(inputs["control"]) == set(inputs["change"]) == set(parent_input) | {"ChangesStockAllocation"}, "table names")
for name in sorted(parent_input):
    if name == "ProblemDescription":
        continue
    for arm in inputs:
        check(inputs[arm][name] == parent_input[name], f"parent table {name}/{arm}")
check(inputs["control"]["ProblemDescription"] == inputs["change"]["ProblemDescription"], "shared description")
for name in sorted(inputs["control"]):
    if name == "ChangesStockAllocation":
        continue
    check(inputs["control"][name] == inputs["change"][name], f"paired table {name}")
check(rows(inputs["control"]["ChangesStockAllocation"]) == [[None] * 6], "control placeholder")
check(rows(inputs["change"]["ChangesStockAllocation"]) == [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "h5 ROSIZ change")
check(cols(inputs["change"]["ChangesStockAllocation"]) == ["POINT", "IID", "STID", "TIMEC", "ROSIZ", "NOTE"], "change schema")
for arm in inputs:
    check(digest(RUN / f"{arm}-input.json") == digest(CASE / f"{arm}-input.json"), f"copied input {arm}")
    exported = tables(RUN / f"{arm}-roundtrip-raw.json", "model")
    authored = [name for name, tab in inputs[arm].items() if rows(tab)]
    check(len(authored) == 22, f"22 row-containing tables {arm}")
    for name in authored:
        check(name in exported, f"roundtrip table {arm}/{name}")
        if name in exported:
            check(cols(inputs[arm][name]) == cols(exported[name]), f"roundtrip columns {arm}/{name}")
            check(rows(inputs[arm][name]) == rows(exported[name]), f"roundtrip rows {arm}/{name}")

parent_log = PARENT_LOG.read_bytes()
reports = {}
parent_report = tables(PARENT_REPORT, "report")
for arm in ("control", "change"):
    log = (RUN / f"{arm}.log").read_bytes()
    check(log == parent_log, f"full native log equals accepted E15: {arm}")
    text = log.decode("utf-8-sig")
    check(not any(5 <= float(m.group(1)) < 10 for m in re.finditer(r"Time: ([0-9.]+) .*?(?:reorder task|Stock at:|Replacement item arrives)", text)), f"no h5-10 reorder/stock action {arm}")
    for needle in (
        "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
        "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>",
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,5>",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>",
        "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>",
        "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,4>",
        "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    ):
        check(needle in text, f"physical event {arm}: {needle[:48]}")
    check(text.count("reorder task 0 started") == 1 and text.count("reorder task 0 completed") == 1, f"one order {arm}")
    check(text.count("mission starting, duration: 2") == 3 and text.count("mission success:") == 2 and text.count("mission aborted:") == 1, f"three mission outcomes {arm}")
    reports[arm] = tables(RUN / f"{arm}-report-raw.json", "report")
    check(set(reports[arm]) == set(parent_report), f"report table set {arm}")
    for name, tab in sorted(parent_report.items()):
        if name == "ProblemDescription":
            continue
        check(cols(reports[arm][name]) == cols(tab), f"report columns {arm}/{name}")
        check(rows(reports[arm][name]) == rows(tab), f"report data {arm}/{name}")
    item = reports[arm]["ItemResults"]
    names = cols(item)
    data = rows(item)
    check(len(data) == 72, f"72 selected ItemResults bins {arm}")
    for i, row in enumerate(data):
        fields = dict(zip(names, row))
        start = i / 2
        check(fields["IID"] == "TEACH-DU-01" and fields["STID"] == "DEPOT-01", f"item selector {arm}/{i}")
        check(fields["STINT"] == start and fields["ETINT"] == start + 0.5, f"item interval {arm}/{i}")
        check(fields["STSZ"] == 4 and fields["NBO"] == 0, f"nominal/backorder {arm}/{i}")
        check(fields["STOHA"] == (3 if start < 10 else 2 if start < 11 else 4), f"physical on-hand {arm}/{i}")
        check(fields["NRO"] == (1 if start == 10 else 0), f"reorder marker {arm}/{i}")
    check(len(rows(reports[arm]["SystemResults"])) == len(rows(reports[arm]["StockTotalResults"])) == len(rows(reports[arm]["MissionResults"])) == 72, f"system/stock/mission bins {arm}")

check((RUN / "control-report-raw.json").read_bytes() == (RUN / "change-report-raw.json").read_bytes(), "paired report bytes equal")
check((RUN / "control.log").read_bytes() == (RUN / "change.log").read_bytes(), "paired native log bytes equal")
verdict = {
    "schema": "simlox-independent-readonly-review/v1",
    "case": "I07.var02 v1.0.0",
    "run_id": RUN.name,
    "verdict": "GO_DIAGNOSTIC_ONLY" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "closure_sha256": digest(RUN / "closure.json"),
    "control_log_sha256": digest(RUN / "control.log"),
    "change_log_sha256": digest(RUN / "change.log"),
    "control_report_sha256": digest(RUN / "control-report-raw.json"),
    "change_report_sha256": digest(RUN / "change-report-raw.json"),
    "observed": "Both arms have identical native event logs and selected reports. No stock event or order follows the h5 change alone; at h10 both order two, delivered h11 as physical IDs 5 and 6.",
    "scope": "One sealed seed and explicit ISTOH3 source. No distinct ROSIZ1 batch-policy effect is observed; the run does not accept the full I07.var02 variant.",
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures[:20]))
    raise SystemExit(1)
