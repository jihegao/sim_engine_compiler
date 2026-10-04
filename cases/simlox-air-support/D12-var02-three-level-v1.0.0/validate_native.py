"""Author read-only replay of the sealed D12.var02 three-level PM run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d12-var02-three-level-v100-ssh-20261004-01"
PARENT = HERE.parent / "D12-var01-active-small-v1.0.0"
PARENT_RUN = PARENT / "runs/d12-var01-active-small-v100-ssh-20261004-01"
failures: list[str] = []
checks = 0


def check(value: bool, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report JSON may contain trailing commas. Never alter raw evidence.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def populated(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        assert name not in result
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert all(len(row) == len(table["columns"]) for row in rows)
            result[name] = {"columns": table["columns"], "rows": rows}
    return result


def report_table(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D12" and contract["variant_id"] == "D12.var02", "contract identity")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(sha(HERE / "contract.json") == closure["source_hashes_before"]["contract"], "contract pin")
check(sha(PARENT / "linked-input.json") == contract["dependency"]["input_sha256"], "parent linked input pin")
check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "parent closure pin")
check(sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["dependency"]["signoff_sha256"], "parent signoff pin")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
source_paths = {
    "contract": HERE / "contract.json",
    "unlinked": HERE / "unlinked-input.json",
    "linked": HERE / "linked-input.json",
    "parent_input": PARENT / "linked-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": HERE / "build.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(source_paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in source_paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
check(len(closure["raw"]) == 22, "raw inventory")
for name, item in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "preserved GUI")
expected_steps = [f"{arm}_{stage}" for arm in ("unlinked", "linked") for stage in ("import", "export", "calc", "report")]
check([step["name"] for step in steps] == expected_steps, "step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {arm: load(HERE / f"{arm}-input.json") for arm in ("unlinked", "linked")}
comparison = json.loads(json.dumps(inputs["unlinked"]))
for table in comparison["model"]["tables"]:
    if table["name"] == "ProblemDescription":
        table["instances"] = next(t for t in inputs["linked"]["model"]["tables"] if t["name"] == "ProblemDescription")["instances"]
    if table["name"] == "MaterielPM":
        cols = [c["name"] for c in table["columns"]]
        for instance in table["instances"]:
            for row in instance["rows"]:
                if row[cols.index("PMID")] == "TOP49":
                    row[cols.index("PMRID")] = "BIG48P5"
check(comparison == inputs["linked"], "paired source differs only in description and TOP49.PMRID")

parent = load(PARENT / "linked-input.json")
for arm in ("unlinked", "linked"):
    expected_child = json.loads(json.dumps(parent))
    tables = {t["name"]: t for t in expected_child["model"]["tables"]}
    appended = {
        "MaterielPM": {"PMID": "TOP49", "DESCR": "49-hour top-level service", "MID": "TEACH-AIR-01", "PMINT": 49.0, "OPID": "CALHOURS", "ATIM": 0.0, "DTIM": 0.0, "PMRID": "BIG48P5" if arm == "linked" else None},
        "PMLocation": {"PMID": "TOP49", "ID": "TEACH-AIR-01", "STID": "BASE-01", "PMT": 1.0, "TID": "PM-TOP49"},
        "Tasks": {"TID": "PM-TOP49", "DESCR": "One-hour top-level service"},
        "TaskBreakDown": {"TID": "PM-TOP49", "SEQ": 1, "SUTID": "INSPECT", "DURN": 1.0},
        "SubTaskResource": {"TID": "PM-TOP49", "SEQ": 1, "RID": "P-MAINT", "QTY": 1, "RPROB": 1.0},
    }
    for name, values in appended.items():
        table = tables[name]
        names = [c["name"] for c in table["columns"]]
        table["instances"][0]["rows"].append([values.get(column) for column in names])
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = f"D12.var02 {arm} TOP49-to-BIG48P5 relation"
    check(inputs[arm] == expected_child, f"{arm} exact accepted-parent delta")

reports = {}
logs = {}
for arm in ("unlinked", "linked"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} source copy")
    exported = load_native(RUN / f"{arm}-roundtrip-raw.json")
    authored = populated(inputs[arm])
    native = populated(exported)
    check(all(native.get(name) == table for name, table in authored.items()), f"{arm} populated rows roundtrip")
    check(len(authored) >= 22, f"{arm} populated tables")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0], f"{arm} converter outcome")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} usable SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} zero converter errors")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "126"], f"{arm} warning classification")
    reports[arm] = load_native(RUN / f"{arm}-report-raw.json")
    logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    for table in ("SystemResults", "ResourceResults", "StockTotalResults"):
        rows = report_table(reports[arm], table)
        check(len(rows) == 120 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(rows)), f"{arm} {table} 120 contiguous bins")
    workers = report_table(reports[arm], "ResourceResults")
    check(all(row["NR"] == row["NRA"] == row["NRN"] == 1 and -0.00002 <= row["NRUM"] <= 1.00002 for row in workers), f"{arm} one-worker capacity")
    check("Time: 20.8819 <TEACH-AIR-01,1> critical random failure added" in logs[arm] and "Time: 26.6319  system DIRP task 0" in logs[arm], f"{arm} actual first-cycle repair")
    check("Time: 24  system PM task 1" in logs[arm] and "Time: 28.6319  system PM task 2" in logs[arm], f"{arm} first-cycle CAL24")
    check("Time: 48  system PM task 3 on <TEACH-AIR-01,1> PMID: CAL24" in logs[arm] and "Time: 48  subtask 3 seqno 1 within system PM task 3 on <TEACH-AIR-01,1> starts performing" in logs[arm], f"{arm} active CAL24 at 48")
    check("Time: 48.5  system PM task 5 on <TEACH-AIR-01,1> PMID: BIG48P5" in logs[arm] and "Time: 48.5  system PM task 6 on <TEACH-AIR-01,0> PMID: BIG48P5" in logs[arm], f"{arm} BIG48P5 due")
    check("Time: 48.5  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> starts performing" in logs[arm], f"{arm} middle PM physically working before TOP49")

check(logs["unlinked"].split("Time: 49 ")[0] == logs["linked"].split("Time: 49 ")[0], "identical pre-49 event trace")
for event in (
    "Time: 49  system PM task 8 on <TEACH-AIR-01,1> PMID: TOP49",
    "Time: 49.5  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> completed",
    "Time: 49.5  subtask 6 seqno 1 within system PM task 6 on <TEACH-AIR-01,0> starts performing",
    "Time: 50.5  subtask 8 seqno 1 within system PM task 8 on <TEACH-AIR-01,1> starts performing",
    "Time: 51.5  subtask 7 seqno 1 within system PM task 7 on <TEACH-AIR-01,0> starts performing",
    "Time: 52.5  system PM task 7 on <TEACH-AIR-01,0> completed",
):
    check(event in logs["unlinked"], f"unlinked {event[:47]}")
for event in (
    "Time: 49  system PM task 8 on <TEACH-AIR-01,1> PMID: TOP49",
    "Time: 49  system PM task 5 on <TEACH-AIR-01,1> stopped",
    "Time: 49  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> ordered to stop",
    "Time: 49  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> frees resources",
    "Time: 49  subtask 7 seqno 1 within system PM task 7 on <TEACH-AIR-01,0> starts performing",
    "Time: 49  system PM task 6 on <TEACH-AIR-01,0> stopped",
    "Time: 49  system PM task 4 on <TEACH-AIR-01,0> stopped",
    "Time: 50  subtask 8 seqno 1 within system PM task 8 on <TEACH-AIR-01,1> starts performing",
    "Time: 51  system PM task 8 on <TEACH-AIR-01,1> completed",
):
    check(event in logs["linked"], f"linked {event[:47]}")
check("Time: 49.5  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> completed" not in logs["linked"], "linked active middle PM interrupted")
check("subtask 4 seqno 1 within system PM task 4 on <TEACH-AIR-01,0> starts performing" not in logs["linked"], "linked waiting small PM never performs")


def worker_spans(log: str) -> list[tuple[float, float]]:
    events = re.findall(r"Time: ([0-9.]+)  <P-MAINT at <BASE-01,0>> (allocated to|deallocated from) +maintenance task: 1  available now: ([01])", log)
    active = None
    spans = []
    for time, action, available in events:
        moment = float(time)
        if action == "allocated to":
            check(active is None and available == "0", f"worker allocation at {moment}")
            active = moment
        else:
            check(active is not None and available == "1", f"worker release at {moment}")
            spans.append((active, moment))
            active = None
    check(active is None, "worker fully released")
    return spans


expected_spans = {
    "unlinked": [(21.6319, 26.6319), (26.6319, 27.6319), (27.6319, 28.6319), (48, 48.5), (48.5, 49.5), (49.5, 50.5), (50.5, 51.5), (51.5, 52.5)],
    "linked": [(21.6319, 26.6319), (26.6319, 27.6319), (27.6319, 28.6319), (48, 48.5), (48.5, 49), (49, 49), (49, 50), (50, 51)],
}
for arm in ("unlinked", "linked"):
    check(worker_spans(logs[arm]) == expected_spans[arm], f"{arm} exact worker leases")

for arm, expected in (("unlinked", (8, 6, 11.5)), ("linked", (8, 4, 10.0))):
    systems = report_table(reports[arm], "SystemResults")
    resources = report_table(reports[arm], "ResourceResults")
    check(sum(row["NPMS"] for row in systems) == expected[0] and sum(row["NPMT"] for row in systems) == expected[1], f"{arm} PM starts/completions")
    check(all(abs(row["NSYA"] + row["NSYUA"] - 2) < 1e-5 for row in systems), f"{arm} available plus unavailable aircraft")
    check(abs(sum(row["NSYPM"] * 0.5 for row in systems) - (expected[2] - 5)) < 1e-4, f"{arm} System PM worker-hours")
    check(abs(sum(row["NSYRP"] * 0.5 for row in systems) - 5) < 1e-4, f"{arm} System repair hours")
    check(abs(sum(row["NRUM"] * 0.5 for row in resources) - expected[2]) < 1e-4, f"{arm} repair plus PM worker-hours")
    total = report_table(reports[arm], "ResourceResultsTotal")[0]
    check(abs(total["NRUM"] * 60 - expected[2]) < 1e-4, f"{arm} resource total reconciles")
check(report_table(reports["unlinked"], "ResultSummary") == report_table(reports["linked"], "ResultSummary"), "same mission summary")
check(report_table(reports["unlinked"], "StockTotalResults") == report_table(reports["linked"], "StockTotalResults"), "same stock trace")

verdict = {
    "schema": "simlox-d12-var02-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "passed": not failures,
    "failures": failures,
    "observed": "In both arms BIG48P5.PMRID=CAL24 stops a performing CAL24 task on aircraft1 at h48.5. With TOP49.PMRID=BIG48P5, TOP49 stops a performing BIG48P5 task on aircraft1 at h49 after 0.5h, and a second BIG48P5 task on aircraft0 starts and stops at h49. Both TOP49 tasks complete. The paired unlinked control completes both BIG48P5 tasks. The linked arm records 4 versus 6 completed PMs and 10.0 versus 11.5 worker hours; inherited missions match between arms.",
    "limits": "One seed, two aircraft, one shared worker and CALHOURS. CAL24 on aircraft0 also stops at h49 in the linked arm, but this does not establish automatic transitive PMRID cancellation or counter reset. No ENFNC, remote-base or general scheduling claim.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for failure in failures:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)
