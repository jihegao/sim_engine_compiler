"""Independent standard-library replay of the E11.var02 sealed boundary panel."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E11-autonomous-support-gap-v1.0.0"
PRUN = PARENT / "runs" / "e11-base-autom-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")
RUNS = {arm: CASE / "runs" / f"e11-var02-{arm}-v100-ssh-20261003-01" for arm in ("before", "at")}


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, value: bool, label: str) -> None:
        if value:
            self.passed += 1
        else:
            self.failures.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.check(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native_report: bool = False) -> dict | list:
    data = path.read_text(encoding="utf-8-sig")
    if native_report:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def tables(path: Path, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in load(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for row in rows(table)]


def event(a: Audit, log: str, hour: str, phrase: str, label: str) -> None:
    a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"{label} h{hour}: {phrase}")


def compare_source(a: Audit, arm: str, path: Path, source: dict[str, dict], parent: dict[str, dict], diff: dict) -> None:
    a.eq(sha(path), diff["arms"][arm]["source_sha256"], f"{arm} diff source pin")
    a.eq(set(source), set(parent), f"{arm} source table names")
    a.eq(len(source), 32, f"{arm} source table count")
    expected_changes = diff["arms"][arm]["changes"]
    a.eq(len(expected_changes), 4, f"{arm} four changed cells")
    a.eq([name for name in sorted(source) if source[name] != parent[name]], ["ProblemDescription", "TransportPolicyProfile"], f"{arm} only two changed tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"{arm} schema {name}")
        if name not in {"ProblemDescription", "TransportPolicyProfile"}:
            a.eq(source[name], parent[name], f"{arm} unchanged {name}")
    for name in ("ProblemDescription", "TransportPolicyProfile"):
        matching = [x for x in expected_changes if x["table"] == name]
        actual = []
        cols = [c["name"] for c in source[name]["columns"]]
        for i, (oldrow, newrow) in enumerate(zip(rows(parent[name]), rows(source[name]))):
            for j, (old, new) in enumerate(zip(oldrow, newrow)):
                if old != new:
                    actual.append((i, cols[j], old, new))
        declared = [(x["row"], x["column"], x["before"], x["after"]) for x in matching]
        a.eq(actual, declared, f"{arm} exact {name} cells")
    policy = records(source["TransportPolicyProfile"])
    expected = (11, 13, 23) if arm == "before" else (10, 12, 24)
    a.eq((policy[0]["DURN"], policy[1]["STIM"], policy[1]["DURN"]), expected, f"{arm} two-hour boundary windows")
    a.eq(policy[0]["STIM"], 0, f"{arm} first window start")
    a.eq(policy[1]["STIM"] + policy[1]["DURN"], 36, f"{arm} second window horizon")


def main() -> dict:
    a = Audit()
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    parent_input = PARENT / "native-input.json"
    parent = tables(parent_input)
    parent_report = tables(PRUN / "report-raw.json", "report")
    parent_log = (PRUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    a.eq(contract["variant_id"], "E11.var02", "contract identity")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "exact diff pin")
    a.eq(sha(parent_input), contract["accepted_parent"]["input_sha256"], "accepted parent source pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "accepted parent index pin")
    a.eq(diff["parent_sha256"], sha(parent_input), "diff parent pin")
    installed = {
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        pin = "simlox_exe_sha256" if key == "simlox_exe" else "manual_pdf_sha256" if key == "manual" else "dictionary_sha256"
        a.eq(sha(path), contract["source"][pin], f"installed {key}")

    observed: dict[str, dict] = {}
    expected_system = {
        20: {"NSYRP": [0.3333333432674408, 1], "NSYWI": [0.6666666865348816, 0], "SYDT": [1.3333333730697632, 0.5]},
        21: {"NSYRY": [0, 1], "NSYUA": [1, 0], "NSYA": [0, 1], "NSYWI": [1, 0], "NREPT": [0, 1]},
        22: {"NSYRY": [0.3333333432674408, 1], "NSYUA": [0.6666666865348816, 0], "NSYA": [0.3333333432674408, 1], "NSYRP": [0.6666666865348816, 0], "NREPT": [1, 0]},
    }
    expected_stock = {
        20: {"NBO": [1, 0], "ROS": [1, 0], "ROST": [1, 0], "WT": [1, 0], "WTT": [1, 0], "WTS": [1, None], "PNB": [0, 1]},
        21: {"NBO": [1, 0], "PNB": [0, 1]},
    }

    for arm in ("before", "at"):
        run = RUNS[arm]
        source_path = CASE / f"native-input-{arm}.json"
        source = tables(source_path)
        compare_source(a, arm, source_path, source, parent, diff)
        a.eq(sha(source_path), contract["arms"][arm]["native_input_sha256"], f"{arm} contract source pin")
        inv = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        exported = tables(run / "roundtrip-raw.json")
        native_report = tables(run / "report-raw.json", "report")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")

        a.eq(inv["run_id"], run.name, f"{arm} run identity")
        a.eq(inv["input_sha256"], sha(source_path), f"{arm} invocation input")
        a.eq(inv["execution_mode"], "ssh_cli_v1", f"{arm} SSH mode")
        a.eq(inv["session_id"], 0, f"{arm} headless session")
        a.check(inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{arm} SSH ancestor")
        a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", f"{arm} queue mutex")
        a.eq(inv["gui"]["pid"], 13340, f"{arm} GUI PID")
        a.eq(inv["gui"]["session_id"], 1, f"{arm} GUI session")
        a.eq(closure["invocation_sha256"], sha(run / "invocation.json"), f"{arm} invocation seal")
        a.eq(closure["source_hashes_before"], closure["source_hashes_after"], f"{arm} source stable")
        a.eq(closure["source_hashes_before"], inv["source_hashes_before"], f"{arm} invocation source pins")
        source_paths = {
            "input": source_path, "parent": parent_input,
            "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json",
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
            **installed,
        }
        for key, path in sorted(source_paths.items()):
            a.eq(closure["source_hashes_before"][key], sha(path), f"{arm} source SHA {key}")
        a.eq(len(closure["raw"]), 12, f"{arm} 12 raw seals")
        for name, meta in sorted(closure["raw"].items()):
            path = run / name
            a.check(path.is_file(), f"{arm} raw exists {name}")
            if path.is_file():
                a.eq(path.stat().st_size, meta["bytes"], f"{arm} raw size {name}")
                a.eq(sha(path), meta["sha256"], f"{arm} raw SHA {name}")
        a.eq(sha(run / "input.json"), sha(source_path), f"{arm} run input copy")
        a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} five steps")
        for step in steps:
            a.eq(step["exit_code"], 0, f"{arm} {step['name']} exit")
            a.eq(step["status"], "completed", f"{arm} {step['name']} status")
            a.check(step["gui_preserved"] is True, f"{arm} {step['name']} GUI preserved")
            a.eq(step["error"], None, f"{arm} {step['name']} error")
        authored = [name for name, t in source.items() if rows(t)]
        a.eq(len(authored), 22, f"{arm} 22 row-containing authored tables")
        a.eq(set(exported), set(source), f"{arm} exported table set")
        for name in sorted(authored):
            a.eq(exported[name], source[name], f"{arm} exact native roundtrip {name}")
        a.check((run / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
        a.eq(re.findall(r"\(error #(\d+)\)", converter), [], f"{arm} zero converter errors")
        a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108", "2076", "2077"], f"{arm} warnings")
        a.check("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in converter, f"{arm} conversion totals")

        for hour, phrase in [
            ("9.8829", "critical random failure added"), ("9.8829", "mission aborted:"),
            ("10", "item requiring maintenance is <TEACH-LRU-01,0,1>"),
            ("10", "Backorder added"), ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
            ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"),
            ("10", "Backorder removed, waiting time was 0"),
            ("10", "subitem received <TEACH-LRU-01,0,0>"),
            ("10.5", "System ready <TEACH-AIR-01,0>"),
        ]:
            event(a, log, hour, phrase, arm)
        a.check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log, f"{arm} physical ID0 reaches BASE h10")
        a.check(log.index("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives") < log.index("Time: 10  transport request <<TEACH-LRU-01,0,0>"), f"{arm} demand precedes downward request")
        a.check(log.index("Time: 10  transport request <<TEACH-LRU-01,0,0>") < log.index("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder removed"), f"{arm} downward request precedes BO clearance")
        for mid, ordered, start, finish in [(0, 7, 8, 10), (1, 19, 20, 22), (2, 31, 32, 34)]:
            identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
            event(a, log, str(ordered), f"{identity} mission created:", arm)
            event(a, log, str(start), f"{identity} mission starting, duration: 2 : <TEACH-AIR-01,0>", arm)
            event(a, log, str(finish), f"{identity} {'aborted mission completed:' if mid == 0 else 'mission completed:'}", arm)
            if mid:
                event(a, log, str(finish), f"{identity} mission success:", arm)
        a.eq(len(re.findall(r"mission aborted:", log)), 1, f"{arm} first mission abort only")
        a.eq(len(re.findall(r"mission success:", log)), 2, f"{arm} two later successes")
        a.check("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log, f"{arm} terminal one ready")

        if arm == "before":
            for hour, phrase in [("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started"), ("10.1667", "Start repair of item <TEACH-LRU-01,0,1>"), ("11.1667", "Finished repair of item <TEACH-LRU-01,0,1>"), ("11.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"), ("13", "scheduled transport task 0 cancelled with 0 items/systems"), ("13", "scheduled transport task 1 cancelled with 0 items/systems")]:
                event(a, log, hour, phrase, arm)
            a.check("Time: 10.1667  transport request <<TEACH-LRU-01,0,1>" in log, "before upward ID1 moves before h11 disconnect")
        else:
            for hour, phrase in [("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0"), ("12", "scheduled transport task 0 starts with 1 items/systems, transport time: 0"), ("12", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started"), ("12", "Start repair of item <TEACH-LRU-01,0,1>"), ("12", "scheduled transport task 1 cancelled with 0 items/systems"), ("13", "Finished repair of item <TEACH-LRU-01,0,1>"), ("13", "Put back replacement item <TEACH-LRU-01,0,1> to stock")]:
                event(a, log, hour, phrase, arm)
            a.check("Time: 10.1667  transport request <<TEACH-LRU-01,0,1>" in log and "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" not in log, "at upward ID1 queues rather than starts h10.1667")

        a.eq(set(native_report), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm} report table set")
        a.eq(rows(native_report["ResultSummary"]), rows(parent_report["ResultSummary"]), f"{arm} summary equal accepted after-control")
        a.eq(records(native_report["ResultSummary"])[0]["MSUF"], 0.6666666865348816, f"{arm} two-of-three success")
        for name, expected in (("SystemResults", expected_system), ("StockTotalResults", expected_stock)):
            got = records(native_report[name]); ref = records(parent_report[name])
            a.eq(len(got), 72, f"{arm} {name} 72 bins")
            a.eq(len(ref), 72, f"{arm} parent {name} 72 bins")
            for i, (row, old) in enumerate(zip(got, ref)):
                a.eq((row["STINT"], row["ETINT"]), (i / 2, (i + 1) / 2), f"{arm} {name} bin {i} clock")
                a.eq((old["STINT"], old["ETINT"]), (i / 2, (i + 1) / 2), f"{arm} parent {name} bin {i} clock")
                delta_actual = {key: [old[key], row[key]] for key in row if old[key] != row[key]}
                a.eq(delta_actual, expected.get(i, {}), f"{arm} entire {name} bin {i} delta")
        system = records(native_report["SystemResults"])
        stock = records(native_report["StockTotalResults"])
        a.eq(sum(r["NSYMO"] * 0.5 for r in system), 6, f"{arm} six aircraft operating hours")
        a.eq(sum(r["NFAIL"] for r in system), 1, f"{arm} one failure marker")
        a.eq(stock[20]["NBO"], 0, f"{arm} no accumulated h10-10.5 BO")
        a.eq(stock[21]["NBO"], 0, f"{arm} no accumulated h10.5-11 BO")
        a.eq(stock[-1]["NBO"], 0, f"{arm} terminal no BO")
        a.eq(system[-1]["NSYRY"], 1, f"{arm} terminal ready one")
        observed[arm] = {"closure_sha256": sha(run / "closure.json"), "upward_failed_id1_started_hour": 10.1667 if arm == "before" else 12, "failed_id1_repaired_hour": 11.1667 if arm == "before" else 13}

    a.check("Time: 11  transport request <<TEACH-LRU-01,0,0>" in parent_log, "after-control downward ID0 waits until h11")
    a.check("Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in parent_log, "after-control ready h11.3333")
    before_rep = tables(RUNS["before"] / "report-raw.json", "report")
    at_rep = tables(RUNS["at"] / "report-raw.json", "report")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.eq(before_rep[name], at_rep[name], f"before/at aggregate {name} equality")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11.var02",
        "passed": not a.failures,
        "verdict": "GO: bounded three-arm h10 boundary observation" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "evidence": {"accepted_after_closure_sha256": sha(PRUN / "closure.json"), "runs": observed, "downward_spare_id0_arrival_hour_both": 10, "before_and_at_ready_hour": 10.5, "after_ready_hour": 11.3333, "source_row_tables_exact_roundtrip_each": 22, "system_stock_report_bins_each": 72},
        "limits": [
            "One h10 demand, one two-hour ONDEM gap per arm, one support link and one seed.",
            "Before and at both have an instantaneous h10 backorder add/remove event but zero accumulated NBO bins; do not describe the physical log as no backorder event.",
            "At-boundary downward ID0 moved at h10 while failed ID1 queued until h12; this direction-specific observed order does not establish a general same-time priority rule.",
            "No h12 or h13 exact-reconnection demand, repeated requests, local stock, GUI visual or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
