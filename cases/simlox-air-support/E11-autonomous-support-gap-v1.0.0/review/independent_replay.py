"""Independent standard-library replay of sealed E11 native evidence; never runs SIMLOX."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
PARENT = BASE / "E10-var03-ondem-support-gap-v1.0.0"
RUN = CASE / "runs" / "e11-base-autom-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e10-var03-gap-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.ok = 0
        self.failures: list[str] = []

    def check(self, value: bool, label: str) -> None:
        if value:
            self.ok += 1
        else:
            self.failures.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.check(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jread(path: Path, trailing_comma: bool = False) -> dict | list:
    data = path.read_text(encoding="utf-8-sig")
    if trailing_comma:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def model(path: Path) -> dict[str, dict]:
    return {table["name"]: table for table in jread(path)["model"]["tables"]}


def report(path: Path) -> dict[str, dict]:
    return {table["name"]: table for table in jread(path, trailing_comma=True)["report"]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event(log: str, time: str, phrase: str, a: Audit) -> None:
    a.check(any(line.startswith(f"Time: {time} ") and phrase in line for line in log.splitlines()), f"event h{time}: {phrase}")


def run() -> dict:
    a = Audit()
    contract = jread(CASE / "contract.json")
    delta = jread(CASE / "exact-diff.json")
    inv = jread(RUN / "invocation.json")
    closure = jread(RUN / "closure.json")
    steps = jread(RUN / "steps.json")
    source = model(CASE / "native-input.json")
    prior = model(PARENT / "native-input.json")
    exported = model(RUN / "roundtrip-raw.json")
    result = report(RUN / "report-raw.json")
    control = report(PRUN / "report-raw.json")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PRUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    conv = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["case_id"], "E11", "case identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "child input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "accepted parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "accepted parent index pin")
    installed = {
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        pin = "manual_pdf_sha256" if key == "manual" else "dictionary_sha256" if key == "dictionary" else "simlox_exe_sha256"
        a.eq(sha(path), contract["source"][pin], f"installed {key} pin")

    a.eq(set(source), set(prior), "same parent and child tables")
    a.eq(len(source), 32, "source table count")
    a.eq(delta["changed_tables"], ["ProblemDescription", "Station", "StationStructure"], "declared table delta")
    actual_changes = []
    for name in sorted(source):
        a.eq(source[name]["columns"], prior[name]["columns"], f"{name} schema unchanged")
        if source[name] != prior[name]:
            actual_changes.append(name)
        if name not in {"ProblemDescription", "Station", "StationStructure"}:
            a.eq(source[name], prior[name], f"{name} unchanged")
    a.eq(actual_changes, sorted(delta["changed_tables"]), "exact changed table set")
    a.eq(len(delta["changes"]), 3, "three changed cells")
    for change in delta["changes"]:
        name = change["table"]
        idx = next(i for i, column in enumerate(source[name]["columns"]) if column["name"] == change["column"])
        a.eq(rows(prior[name])[change["row"]][idx], change["before"], f"{name}.{change['column']} parent value")
        a.eq(rows(source[name])[change["row"]][idx], change["after"], f"{name}.{change['column']} child value")
        parent_rows = rows(prior[name]); child_rows = rows(source[name])
        changes = [(i, j) for i, (x, y) in enumerate(zip(parent_rows, child_rows)) for j, (old, new) in enumerate(zip(x, y)) if old != new]
        a.eq(changes, [(change["row"], idx)], f"{name} has one changed cell")
    a.eq(records(source["Station"])[0]["TYPE"], "AUTOM", "BASE station autonomous type")
    a.eq(rows(source["TransportPolicyProfile"]), rows(prior["TransportPolicyProfile"]), "h0-9 and h11-36 policy unchanged")

    a.eq(inv["run_id"], RUN.name, "run identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invocation input seal")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH native mode")
    a.eq(inv["session_id"], 0, "session zero")
    a.check(inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestor")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "host queue mutex")
    a.eq(inv["gui"]["pid"], 13340, "GUI identity")
    a.eq(inv["gui"]["session_id"], 1, "GUI separate session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation SHA closure")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source frozen across run")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "invocation/closure source agreement")
    source_paths = {
        "input": CASE / "native-input.json", "parent": PARENT / "native-input.json",
        "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json",
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        **installed,
    }
    for key, path in sorted(source_paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"source seal {key}")
    for name, entry in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, entry["bytes"], f"raw size {name}")
            a.eq(sha(path), entry["sha256"], f"raw SHA {name}")
    a.eq(len(closure["raw"]), 12, "12 sealed native artifacts")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copy")
    a.eq([step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five native/check steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} completed")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} step error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 22, "22 row-containing authored tables")
    a.eq(set(exported), set(source), "export table set")
    for name in sorted(authored):
        a.eq(exported[name], source[name], f"exact native roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid nontrivial SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", conv), [], "no converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", conv), ["108", "2076", "2077"], "all converter warnings")
    a.check("TFRMS ignored for autonomous mission station: BASE-01" in conv, "autonomous TFRMS warning text")
    a.check("TTOMS ignored for autonomous mission station: BASE-01" in conv, "autonomous TTOMS warning text")
    a.check("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in conv, "converter counts")

    for time, phrase in [
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted:"),
        ("10", "aborted mission completed:"), ("10", "Backorder added"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "attached to  scheduled transport task 1"),
        ("10.1667", "fit subitem subtask 1 seqno 2"),
        ("10.1667", "attached to  scheduled transport task 0"),
        ("11", "scheduled transport task 0 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 0 arrives with 1 items/systems"),
        ("11", "scheduled transport task 1 arrives with 1 items/systems"),
        ("11", "Backorder removed, waiting time was 1"),
        ("11", "subitem received <TEACH-LRU-01,0,0>"),
        ("11", "Start repair of item <TEACH-LRU-01,0,1>"),
        ("11.3333", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
        ("11.3333", "System ready <TEACH-AIR-01,0>"),
        ("12", "Finished repair of item <TEACH-LRU-01,0,1>"),
        ("12", "Put back replacement item <TEACH-LRU-01,0,1> to stock"),
    ]:
        event(log, time, phrase, a)
    a.check("Time: 11  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "failed ID1 outward at reconnection")
    a.check("Time: 11  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "spare ID0 inward at reconnection")
    a.eq(len(re.findall(r"^Time: (?:9(?:\.\d+)?|10(?:\.\d+)?) .*transport request .* started", log, re.M)), 0, "no h9-11 physical transport request starts")
    a.eq(len(re.findall(r"^Time: (?:9(?:\.\d+)?|10(?:\.\d+)?) .*scheduled transport task \d+ arrives", log, re.M)), 0, "no h9-11 transport arrivals")
    a.check("Time: 13 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in parent_log, "parent ordinary spare arrival h13")
    a.check("Time: 13.3333 <TEACH-AIR-01,BASE-01,0> System ready" in parent_log, "parent ordinary ready h13.3333")
    for mid, ordered, started, finished in [(0, 7, 8, 10), (1, 19, 20, 22), (2, 31, 32, 34)]:
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        event(log, str(ordered), f"{mission} mission created:", a)
        event(log, str(started), f"{mission} mission starting, duration: 2 : <TEACH-AIR-01,0>", a)
        ending = "aborted mission completed:" if mid == 0 else "mission completed:"
        event(log, str(finished), f"{mission} {ending}", a)
        if mid:
            event(log, str(finished), f"{mission} mission success:", a)
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "one mission abortion")
    a.eq(len(re.findall(r"mission success:", log)), 2, "two mission successes")
    a.eq(len(re.findall(r"requests resources: no resources needed", log)), 3, "no resources in three subtasks")
    a.check("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log, "terminal one aircraft ready")
    a.check("Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log, "depot item restored")
    a.check("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 0" in log, "backorder cleared")

    a.eq(set(result), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table inventory")
    a.eq(rows(result["ResultSummary"]), rows(control["ResultSummary"]), "summary same as parent")
    a.eq(records(result["ResultSummary"])[0]["MSUF"], 0.6666666865348816, "two of three missions succeed")
    for name in ("SystemResults", "StockTotalResults"):
        got = records(result[name]); ref = records(control[name])
        a.eq(len(got), 72, f"{name} 72 bins")
        a.eq(len(ref), 72, f"parent {name} 72 bins")
        for i, (row, old) in enumerate(zip(got, ref)):
            a.eq((row["STINT"], row["ETINT"]), (i / 2, (i + 1) / 2), f"{name} bin {i} time")
            a.eq((old["STINT"], old["ETINT"]), (i / 2, (i + 1) / 2), f"parent {name} bin {i} time")
    expected_system_deltas = {
        20: {"SYDT": [3.3333332538604736, 1.3333333730697632]},
        22: {"NSYRY": [0, 0.3333333432674408], "NSYUA": [1, 0.6666666865348816], "NSYA": [0, 0.3333333432674408], "NSYRP": [0, 0.6666666865348816], "NSYWI": [1, 0], "NREPT": [0, 1]},
        23: {"NSYRY": [0, 1], "NSYUA": [1, 0], "NSYA": [0, 1], "NSYWI": [1, 0]},
        24: {"NSYRY": [0, 1], "NSYUA": [1, 0], "NSYA": [0, 1], "NSYWI": [1, 0]},
        25: {"NSYRY": [0, 1], "NSYUA": [1, 0], "NSYA": [0, 1], "NSYWI": [1, 0]},
        26: {"NSYRY": [0.3333333432674408, 1], "NSYUA": [0.6666666865348816, 0], "NSYA": [0.3333333432674408, 1], "NSYRP": [0.6666666865348816, 0], "NREPT": [1, 0]},
    }
    expected_stock_deltas = {
        20: {"WT": [3, 1], "WTT": [3, 1], "WTS": [3, 1]},
        22: {"NBO": [1, 0], "PNB": [0, 1]},
        23: {"NBO": [1, 0], "PNB": [0, 1]},
        24: {"NBO": [1, 0], "PNB": [0, 1]},
        25: {"NBO": [1, 0], "PNB": [0, 1]},
    }
    for name, expected in (("SystemResults", expected_system_deltas), ("StockTotalResults", expected_stock_deltas)):
        got = records(result[name]); ref = records(control[name])
        for i, (row, old) in enumerate(zip(got, ref)):
            actual = {key: [old[key], row[key]] for key in row if row[key] != old[key]}
            a.eq(actual, expected.get(i, {}), f"{name} parent-to-child complete bin {i} delta")
    system = records(result["SystemResults"])
    stock = records(result["StockTotalResults"])
    a.eq(sum(row["NSYMO"] * 0.5 for row in system), 6, "six aircraft operating hours")
    a.eq(sum(row["NFAIL"] for row in system), 1, "one observed failure marker")
    a.eq(stock[20]["NBO"], 1, "backorder in h10-10.5 bin")
    a.eq(stock[21]["NBO"], 1, "backorder in h10.5-11 bin")
    a.eq(stock[22]["NBO"], 0, "backorder cleared at h11")
    a.eq(stock[-1]["NBO"], 0, "terminal report no backorder")
    a.eq(system[-1]["NSYRY"], 1, "terminal report ready aircraft")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded autonomous support-gap observation" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.ok,
        "checks_total": a.ok + len(a.failures),
        "failures": a.failures,
        "evidence": {
            "run_closure_sha256": sha(RUN / "closure.json"),
            "parent_closure_sha256": sha(PRUN / "closure.json"),
            "source_row_tables_exact_roundtrip": len(authored),
            "report_bins_each": 72,
            "converter_warnings": [108, 2076, 2077],
            "reconnection_hour": 11,
            "autonomous_travel_hours": 0,
            "ordinary_parent_spare_arrival_hour": 13,
            "backorder_hours": 1,
            "ready_hour": 11.3333,
            "depot_restock_hour": 12,
        },
        "limits": [
            "One empty local stock, one depot spare, one h9-11 gap, one h10 demand, one support link and one seed.",
            "Warnings 2076/2077 say the ordinary station transport times are ignored for this autonomous BASE-01; the exact zero-duration movements are observed in the native event log.",
            "The report is aggregate. Physical item identity and transport direction are established from this run's native event log.",
            "No locally stocked arm, exact-boundary demand, other policy windows, lateral route, GUI visual, or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = run()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
