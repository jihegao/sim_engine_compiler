"""Author read-only replay of the sealed D12.var03 ENFNC N/Y native pair."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d12-var03-enfnc-v102-ssh-20261004-01"
PARENT = HERE.parent / "D08-var03-criticality-v1.0.0"
PARENT_RUN = PARENT / "runs/d08-var03-failure-mode-v100-ssh-20261002-01"
PATTERN = HERE.parent / "D05-maintenance-competition-v1.0.0"
DIAG0 = HERE.parent / "D12-var03-enfnc-v1.0.0/runs/d12-var03-enfnc-v100-ssh-20261004-01"
DIAG1 = HERE.parent / "D12-var03-enfnc-v1.0.1/runs/d12-var03-enfnc-v101-ssh-20261004-01"
checks = 0
failures: list[str] = []


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
        # The native report can contain trailing commas. Parse a copy only.
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


def cell(doc: dict, table_name: str, row_number: int, column_name: str) -> object:
    table = next(t for t in doc["model"]["tables"] if t["name"] == table_name)
    index = [c["name"] for c in table["columns"]].index(column_name)
    return table["instances"][0]["rows"][row_number][index]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D12" and contract["variant_id"] == "D12.var03" and contract["version"] == "1.0.2-candidate", "contract identity")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
check(sha(PARENT / "native-input-failure-mode.json") == contract["dependency"]["input_sha256"], "accepted parent input")
check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "accepted parent closure")
check(sha(PARENT / "cli-scope-signoff-2026-10-02.md") == contract["dependency"]["signoff_sha256"], "accepted parent signoff")
check(sha(PATTERN / "native-input.json") == contract["dependency"]["maintenance_pattern_input_sha256"], "D05 pattern input")
check(sha(PATTERN / "cli-scope-signoff-2026-09-30.md") == contract["dependency"]["maintenance_pattern_signoff_sha256"], "D05 pattern signoff")
check(sha(DIAG0 / "closure.json") == contract["excluded_diagnostic"]["closure_sha256"], "converter diagnostic sealed")
check(sha(DIAG1 / "closure.json") == contract["excluded_no_exposure_diagnostic"]["closure_sha256"], "no-exposure diagnostic sealed")

sources = {
    "contract": HERE / "contract.json",
    "n": HERE / "n-input.json",
    "y": HERE / "y-input.json",
    "parent_input": PARENT / "native-input-failure-mode.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "pattern_input": PATTERN / "native-input.json",
    "pattern_signoff": PATTERN / "cli-scope-signoff-2026-09-30.md",
    "diagnostic_closure": DIAG0 / "closure.json",
    "no_exposure_closure": DIAG1 / "closure.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": HERE / "build.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(sources) == set(closure["source_hashes_before"]), "source inventory")
for name, path in sources.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][name], f"source seal {name}")
check(len(closure["raw"]) == 22, "raw inventory")
for name, item in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ("n", "y") for stage in ("import", "export", "calc", "report")], "step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {arm: load(HERE / f"{arm}-input.json") for arm in ("n", "y")}
compare = copy.deepcopy(inputs["n"])
for table in compare["model"]["tables"]:
    if table["name"] == "ProblemDescription":
        table["instances"][0]["rows"][0][0] = cell(inputs["y"], "ProblemDescription", 0, "PDESC")
    elif table["name"] == "MaterielPM":
        index = [c["name"] for c in table["columns"]].index("ENFNC")
        table["instances"][0]["rows"][0][index] = "Y"
check(compare == inputs["y"], "N/Y pair differs only in description and ENFNC")
check(cell(inputs["n"], "MaterielPM", 0, "ENFNC") == "N" and cell(inputs["y"], "MaterielPM", 0, "ENFNC") == "Y", "explicit N/Y")
for arm in ("n", "y"):
    check(cell(inputs[arm], "Control", 0, "ENPM") == "Y" and cell(inputs[arm], "Control", 0, "SIMPE") == 14.0, f"{arm} PM enabled and horizon")
    check(cell(inputs[arm], "MaterielPM", 0, "PMINT") == 9.9 and cell(inputs[arm], "MaterielPM", 0, "DTIM") == 0.5, f"{arm} noncritical PM interval")
    check(cell(inputs[arm], "FailureMode", 0, "FRQ") == 3000000 and cell(inputs[arm], "FailureMode", 0, "CRITF") == 0, f"{arm} explicit noncritical failure")
    check(len(next(t for t in inputs[arm]["model"]["tables"] if t["name"] == "OperationProfile")["instances"][0]["rows"]) == 1, f"{arm} single in-window mission")

reports: dict[str, dict] = {}
logs: dict[str, str] = {}
for arm in ("n", "y"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input copy")
    exported = load_native(RUN / f"{arm}-roundtrip-raw.json")
    authored = populated(inputs[arm])
    native = populated(exported)
    check(all(native.get(name) == table for name, table in authored.items()), f"{arm} authored roundtrip")
    check(len(authored) == 26 and sum(len(t["rows"]) for t in authored.values()) == 34, f"{arm} row inventory")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0], f"{arm} converter outcome")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} usable SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and re.findall(r"\(warning #(\d+)\)", runlog) == ["108"], f"{arm} warning classification")
    reports[arm] = load_native(RUN / f"{arm}-report-raw.json")
    logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    for table in ("SystemResults", "ResourceResults", "StockTotalResults"):
        rows = report_table(reports[arm], table)
        check(len(rows) == 28 and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(rows)), f"{arm} {table} 28 half-hour bins")
    system = report_table(reports[arm], "SystemResults")
    resource = report_table(reports[arm], "ResourceResults")
    stock = report_table(reports[arm], "StockTotalResults")
    check(all(abs(row["NSYA"] + row["NSYUA"] - 1) < 1e-5 for row in system), f"{arm} one aircraft")
    check(all(row["NR"] == row["NRA"] == row["NRN"] == 1 and -1e-5 <= row["NRUM"] <= 1 + 1e-5 for row in resource), f"{arm} one worker")
    check(sum(row["NFAIL"] for row in system) == sum(row["NREPT"] for row in system) == sum(row["NPMS"] for row in system) == sum(row["NPMT"] for row in system) == 1, f"{arm} failure/CM/PM markers")
    check(abs(sum(row["NSYPM"] * .5 for row in system) - 1) < 1e-5 and abs(sum(row["NSYRP"] * .5 for row in system) - .5) < 1e-5, f"{arm} PM and CM aircraft-hours")
    check(abs(sum(row["NRUM"] * .5 for row in resource) - 1.5) < 1e-5 and abs(report_table(reports[arm], "ResourceResultsTotal")[0]["NRUM"] * 14 - 1.5) < 1e-5, f"{arm} worker-hours")
    check(system[-1]["NSYRY"] == 1 and resource[-1]["NRUM"] == 0 and stock[-1]["NBO"] == 0, f"{arm} terminal state")
    check("Time: 8.31325 <TEACH-AIR-01,0> noncritical CM failure mode added" in logs[arm] and "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in logs[arm], f"{arm} one noncritical mission failure")
    check(".PM9P9 Non-Critical" in logs[arm] and "Time: 10  system PM task 0 on <TEACH-AIR-01,0> PMID: PM9P9" in logs[arm], f"{arm} noncritical PM pending at return")
    check("< system CM task 1 on <TEACH-AIR-01,0>, NC, 0.5>" in logs[arm], f"{arm} noncritical CM pending at return")

check(logs["n"].split("Time: 10 ")[0] == logs["y"].split("Time: 10 ")[0], "identical pre-return event trace")


def worker_spans(log: str) -> list[tuple[float, float]]:
    events = re.findall(r"Time: ([0-9.]+)  <P-MAINT at <BASE-01,0>> (allocated to|deallocated from) +maintenance task: 1  available now: ([01])", log)
    spans: list[tuple[float, float]] = []
    active: float | None = None
    for time, action, available in events:
        moment = float(time)
        if action == "allocated to":
            check(active is None and available == "0", f"worker allocation {moment}")
            active = moment
        else:
            check(active is not None and available == "1", f"worker release {moment}")
            spans.append((active, moment))
            active = None
    check(active is None, "worker fully released")
    return spans


check(worker_spans(logs["n"]) == [(10.0, 11.0), (11.0, 11.5)], "N PM then CM worker leases")
check(worker_spans(logs["y"]) == [(10.0, 10.5), (10.5, 11.5)], "Y CM then PM worker leases")
for arm, first, second in (("n", "PM", "CM"), ("y", "CM", "PM")):
    first_work = "subtask 0 seqno 1 within system PM task 0" if first == "PM" else "direct repair subtask 1 seqno 1 within system CM task 1"
    second_work = "subtask 0 seqno 1 within system PM task 0" if second == "PM" else "direct repair subtask 1 seqno 1 within system CM task 1"
    check(f"Time: 10  {first_work} on <TEACH-AIR-01,0> starts performing" in logs[arm], f"{arm} first work {first}")
    check(f"Time: {11 if arm == 'n' else 10.5}  {second_work} on <TEACH-AIR-01,0> starts performing" in logs[arm], f"{arm} second work {second}")
    check(logs[arm].index(f"Time: 10  {first_work} on <TEACH-AIR-01,0> starts performing") < logs[arm].index(f"Time: {11 if arm == 'n' else 10.5}  {second_work} on <TEACH-AIR-01,0> starts performing"), f"{arm} physical order")

n_system = report_table(reports["n"], "SystemResults")
y_system = report_table(reports["y"], "SystemResults")
for i, n_pm, n_rp, y_pm, y_rp in ((20, 1, 0, 0, 1), (21, 1, 0, 1, 0), (22, 0, 1, 1, 0)):
    check((n_system[i]["NSYPM"], n_system[i]["NSYRP"], y_system[i]["NSYPM"], y_system[i]["NSYRP"]) == (n_pm, n_rp, y_pm, y_rp), f"bin {i} task order")
check(report_table(reports["n"], "ResultSummary") == report_table(reports["y"], "ResultSummary"), "same mission summary")
check(report_table(reports["n"], "StockTotalResults") == report_table(reports["y"], "StockTotalResults"), "same stock trace")

verdict = {
    "schema": "simlox-d12-var03-enfnc-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "passed": not failures,
    "failures": failures,
    "observed": "With identical noncritical failure at h8.31325 and noncritical PM pending at h10 return, ENFNC=N performs PM h10-11 then CM h11-11.5; ENFNC=Y performs CM h10-10.5 then PM h10.5-11.5. One shared worker is continuously occupied h10-11.5 in both. PM and CM native task start events both occur at h10, so the isolated difference is physical work order, not the existence or timestamp of task starts.",
    "limits": "One fixed seed, one aircraft/base/worker, one explicit failure mode, one PM and one first mission. No general ENFNC priority law, critical PM/failure interaction, PMRID, counter reset, remote-base, GUI or cross-engine claim. v1.0.0/#204 and v1.0.1/no-failure runs are excluded diagnostics.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for failure in failures:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)
