"""Read-only author replay of the sealed D12.var04 remote-critical PM pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d12-var04-remote-critical-v101-ssh-20261004-01"
PARENT = HERE.parent / "D12-var01-active-small-v1.0.0"
PARENT_RUN = PARENT / "runs/d12-var01-active-small-v100-ssh-20261004-01"
DIAG = HERE.parent / "D12-var04-remote-critical-v1.0.0"
DIAG_RUN = DIAG / "runs/d12-var04-remote-critical-v100-ssh-20261004-01"
failed: list[str] = []
checks = 0


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failed.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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


def populated(doc):
    result = {}
    for table in doc["model"]["tables"]:
        rs = [row for instance in table["instances"] for row in instance["rows"]]
        if rs:
            result[table["name"]] = {"columns": table["columns"], "rows": rs}
    return result


def report_rows(report, name):
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D12" and contract["variant_id"] == "D12.var04" and contract["version"] == "1.0.1-candidate", "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
source_paths = {
    "contract": HERE / "contract.json",
    "local": HERE / "local-input.json",
    "remote": HERE / "remote-input.json",
    "diagnostic_closure": DIAG_RUN / "closure.json",
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
check(sha(DIAG_RUN / "closure.json") == contract["excluded_diagnostic"]["closure_sha256"], "diagnostic link")
check(sha(PARENT / "linked-input.json") == contract["dependency"]["input_sha256"], "parent input link")
check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "parent closure link")
check(sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["dependency"]["signoff_sha256"], "parent signoff link")
check(len(closure["raw"]) == 22, "raw inventory count")
for name, item in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session zero SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
check([s["name"] for s in steps] == [f"{a}_{b}" for a in ("local", "remote") for b in ("import", "export", "calc", "report")], "step sequence")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {arm: load(HERE / f"{arm}-input.json") for arm in ("local", "remote")}
diff = []
for lt, rt in zip(inputs["local"]["model"]["tables"], inputs["remote"]["model"]["tables"]):
    assert lt["name"] == rt["name"] and lt["columns"] == rt["columns"]
    for li, ri in zip(lt["instances"], rt["instances"]):
        for lr, rr in zip(li["rows"], ri["rows"]):
            for col, lv, rv in zip(lt["columns"], lr, rr):
                if lv != rv:
                    diff.append((lt["name"], col["name"], lv, rv))
check(diff == [("ProblemDescription", "PDESC", "D12.var04 local critical-small PM boundary", "D12.var04 remote critical-small PM boundary"), ("PMLocation", "STID", "BASE-01", "BASE-02")], "pair-only location difference")

logs = {}
reports = {}
for arm in ("local", "remote"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input pin/copy")
    exported = native(RUN / f"{arm}-roundtrip-raw.json")
    authored = populated(inputs[arm])
    observed = populated(exported)
    check(all(observed.get(name) == table for name, table in authored.items()), f"{arm} populated roundtrip")
    check(len(authored) >= 22, f"{arm} populated table count")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0], f"{arm} converter outcome")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} usable SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "126"], f"{arm} only classified warnings")
    logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    reports[arm] = native(RUN / f"{arm}-report-raw.json")
    for table_name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        rs = report_rows(reports[arm], table_name)
        check(len(rs) == 60 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rs)), f"{arm} {table_name} 60 bins")
    system = report_rows(reports[arm], "SystemResults")
    check(all(abs(r["NSYA"] + r["NSYUA"] - 2) < 1e-5 for r in system), f"{arm} aircraft conservation")
    check("critical random failure added" not in logs[arm], f"{arm} no inherited failure confound")

for aircraft in (0, 1):
    local_small = f"system PM task {1-aircraft} on <TEACH-AIR-01,{aircraft}>"
    remote_small = local_small
    check(f"Time: 24  {local_small} PMID: CAL24" in logs["local"], f"local CAL24 due aircraft {aircraft}")
    check(f"Time: 24  subtask {1-aircraft} seqno 1 within {local_small} starts performing" in logs["local"], f"local CAL24 work aircraft {aircraft}")
    check(f"Time: 24.75  {local_small} stopped" in logs["local"], f"local CAL24 stopped aircraft {aircraft}")
    check(f"Time: 24.25  {remote_small} PMID: CAL24" in logs["remote"], f"remote CAL24 started aircraft {aircraft}")
    check(f"Time: 24.25  subtask {1-aircraft} seqno 1 within {remote_small} starts performing" in logs["remote"], f"remote CAL24 work aircraft {aircraft}")
    check(f"Time: 25.25  subtask {1-aircraft} seqno 1 within {remote_small} completed" in logs["remote"], f"remote CAL24 completion aircraft {aircraft}")
    check(f"{remote_small} stopped" not in logs["remote"], f"remote CAL24 not stopped aircraft {aircraft}")
    big = f"system PM task {2+1-aircraft} on <TEACH-AIR-01,{aircraft}> PMID: BIG24P75"
    check(f"Time: 24.75  {big}" in logs["local"], f"local BIG24P75 start aircraft {aircraft}")
    check(f"Time: 25.5  {big}" in logs["remote"], f"remote BIG24P75 after return aircraft {aircraft}")
check("Time: 24.25 <TEACH-AIR-01,BASE-02,0> System requring maintenance arrives" in logs["remote"], "remote arrival")
check("Time: 25.5 <TEACH-AIR-01,BASE-01,0> Maintained system arrives" in logs["remote"], "remote return")
check("Time: 24.75  system PM task 2" not in logs["remote"] and "Time: 24.75  system PM task 3" not in logs["remote"], "remote larger task deferred")

for arm, expected_pm_hours, expected_done in (("local", 3.5, 2), ("remote", 4.0, 4)):
    sys = report_rows(reports[arm], "SystemResults")
    resource = report_rows(reports[arm], "ResourceResults")
    pm_hours = sum(r["NSYPM"] * 0.5 for r in sys)
    check(abs(pm_hours - expected_pm_hours) < 1e-5, f"{arm} PM aircraft-hours {pm_hours}")
    check(sum(r["NPMS"] for r in sys) == 4 and sum(r["NPMT"] for r in sys) == expected_done, f"{arm} PM starts/completions")
    check(all(r["NSYA"] == 2 for r in sys[-5:]), f"{arm} terminal ready aircraft")
    check(all(r["NR"] == r["NRA"] == r["NRN"] == 4 and -0.00002 <= r["NRUM"] <= 2.00002 for r in resource), f"{arm} four-worker inventory and two-worker load")
    check(abs(sum(r["NRUM"] * 0.5 for r in resource) - expected_pm_hours) < 0.0001, f"{arm} resource integral")
    total = report_rows(reports[arm], "ResourceResultsTotal")[0]
    check(total["NR"] == 4 and abs(total["NRUM"] * 30 - expected_pm_hours) < 0.0001, f"{arm} resource total")
    check(report_rows(reports[arm], "ResultSummary") == report_rows(reports["local"], "ResultSummary"), f"{arm} mission summary")
check(report_rows(reports["local"], "StockTotalResults") == report_rows(reports["remote"], "StockTotalResults"), "same stock trace")

verdict = {
    "schema": "simlox-d12-var04-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failed),
    "checks_total": checks,
    "passed": not failed,
    "failures": failed,
    "observed": "Local critical CAL24 performs at BASE-01 from h24 to h24.75 and is stopped when noncritical BIG24P75 starts. Remote critical CAL24 performs at BASE-02 from h24.25 to h25.25, returns h25.5, and only then does BIG24P75 start. No remote stop event or internal stop attempt is logged.",
    "limits": "Two aircraft, one seed, fixed transport/worker allocation; no internal counter or generalized PM scheduling inference.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for reason in failed:
    print(reason)
raise SystemExit(0 if verdict["passed"] else 1)
