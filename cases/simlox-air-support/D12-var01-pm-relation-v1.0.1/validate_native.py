"""Author read-only replay of the sealed D12.var01 paired native CLI run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d12-var01-pm-relation-v101-ssh-20261004-01"
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0"
PARENT_RUN = PARENT / "runs/d05-pilot-v100-ssh-20260930-03"
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
check(contract["case_id"] == "D12" and contract["variant_id"] == "D12.var01", "contract identity")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(sha(HERE / "contract.json") == closure["source_hashes_before"]["contract"], "contract pin")
check(sha(PARENT / "native-input.json") == contract["dependency"]["input_sha256"], "parent input pin")
check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "parent closure pin")
check(sha(PARENT / "cli-scope-signoff-2026-09-30.md") == contract["dependency"]["signoff_sha256"], "parent signoff pin")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
source_paths = {
    "contract": HERE / "contract.json",
    "unlinked": HERE / "unlinked-input.json",
    "linked": HERE / "linked-input.json",
    "parent_input": PARENT / "native-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
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
                if row[cols.index("PMID")] == "BIG47":
                    row[cols.index("PMRID")] = "CAL24"
check(comparison == inputs["linked"], "paired source differs only in description and BIG47.PMRID")

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
    check("Time: 20.74 <TEACH-AIR-01,1> critical random failure added" in logs[arm] and "Time: 26.4799  system DIRP task 0" in logs[arm], f"{arm} actual first-cycle repair")
    check("Time: 24  system PM task 1" in logs[arm] and "Time: 28.4799  system PM task 2" in logs[arm], f"{arm} first-cycle CAL24")
    check("Time: 47  system PM task 3" in logs[arm] and "Time: 49  system PM task 4" in logs[arm], f"{arm} BIG47")

check(logs["unlinked"].split("Time: 47 ")[0] == logs["linked"].split("Time: 47 ")[0], "identical pre-47 event trace")
for event in (
    "Time: 48  system PM task 5 on <TEACH-AIR-01,1> started",
    "Time: 48  system PM task 6 on <TEACH-AIR-01,0> started",
    "Time: 49  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,1> starts performing",
    "Time: 50  subtask 6 seqno 1 within system PM task 6 on <TEACH-AIR-01,0> starts performing",
):
    check(event in logs["unlinked"], f"unlinked {event[:47]}")
for event in (
    "Time: 48  system PM task 5 on <TEACH-AIR-01,0> started",
    "Time: 49  system PM task 5 on <TEACH-AIR-01,0> stopped",
    "Time: 49  subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,0> ordered to stop",
):
    check(event in logs["linked"], f"linked {event[:47]}")
check("system PM task 6" not in logs["linked"] and "subtask 5 seqno 1 within system PM task 5 on <TEACH-AIR-01,0> starts performing" not in logs["linked"], "linked second CAL24 has no work")

for arm, expected in (("unlinked", (6, 6, 11.0)), ("linked", (5, 4, 9.0))):
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
    "schema": "simlox-d12-var01-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "passed": not failures,
    "failures": failures,
    "observed": "Linked BIG47.PMRID=CAL24 suppresses the two second-cycle CAL24 worker-hours: one small task never starts and one starts at h48 but stops at h49 before work. Control completes both h49-51. First-cycle native repair is h21.4799-26.4799, different from D05 parent.",
    "limits": "Single seed, two aircraft, one worker, CALHOURS; no physically performing small-PM interruption, multi-level, ENFNC, or remote-base claim.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for failure in failures:
    print(failure)
raise SystemExit(0 if verdict["passed"] else 1)
