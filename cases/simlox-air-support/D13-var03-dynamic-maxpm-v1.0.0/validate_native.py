"""Read-only author replay of sealed D13 dynamic MAXPM evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d13-dynamic-maxpm-v100-ssh-20261004-01"
PARENT = HERE.parent / "D13-var02-maxpm-two-v1.0.0"
PARENT_RUN = PARENT / "runs/d13-maxpm-two-v100-ssh-20260930-01"
failed: list[str] = []
checks = 0


def check(ok: bool, label: str):
    global checks
    checks += 1
    if not ok:
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


def table(doc, name):
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def populated(doc):
    return {t["name"]: {"columns": t["columns"], "rows": [r for i in t["instances"] for r in i["rows"]]}
            for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}


def report_rows(doc, name):
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for i in t["instances"] for row in i["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D13" and contract["variant_ids"] == ["D13.var03"], "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json",
    "rise": HERE / "rise-input.json",
    "hold": HERE / "hold-input.json",
    "parent_input": PARENT / "native-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": HERE / "build.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
for key in ("parent_input", "parent_closure", "parent_signoff"):
    check(closure["source_hashes_before"][key] == contract["dependency"][key + "_sha256"], f"parent pin {key}")
check(closure["source_hashes_before"]["manual"] == contract["manual"]["sha256"], "manual pin")
check(len(closure["raw"]) == 22, "raw count")
for name, item in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session zero")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host queue")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([s["name"] for s in steps] == [f"{a}_{stage}" for a in ("rise", "hold") for stage in ("import", "export", "calc", "report")], "step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {a: load(HERE / f"{a}-input.json") for a in ("rise", "hold")}
delta = []
for rt, ht in zip(inputs["rise"]["model"]["tables"], inputs["hold"]["model"]["tables"]):
    assert rt["name"] == ht["name"] and rt["columns"] == ht["columns"]
    for ri, hi in zip(rt["instances"], ht["instances"]):
        for rr, hr in zip(ri["rows"], hi["rows"]):
            for col, rv, hv in zip(rt["columns"], rr, hr):
                if rv != hv:
                    delta.append((rt["name"], col["name"], rv, hv))
check(delta == [("ProblemDescription", "PDESC", "D13.var03 MaxPMProfile 0-1-2", "D13.var03 MaxPMProfile 0-1-1"),
                ("MaxPMProfile", "MAXPM", 2, 1)], "paired source delta")

reports = {}
logs = {}
for arm, final_limit in (("rise", 2), ("hold", 1)):
    source = inputs[arm]
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input seal")
    unit = table(source, "Unit")
    names = [c["name"] for c in unit["columns"]]
    cells = unit["instances"][0]["rows"][0]
    check(cells[names.index("MAXPM")] == 0 and cells[names.index("MAXPMP")] == "CAP24", f"{arm} profile reference")
    profile = table(source, "MaxPMProfile")
    check(profile["instances"][0]["rows"] == [
        ["CAP24", "<LIMIT>", 0.0, 24.25, 1, 0.0, 0, None],
        ["CAP24", "<LIMIT>", 24.25, 24.75, 1, 0.0, 1, None],
        ["CAP24", "<LIMIT>", 24.75, 36.0, 1, 0.0, final_limit, None]], f"{arm} profile rows")
    check(len(populated(source)) == 19 and sum(len(t["rows"]) for t in populated(source).values()) == 24, f"{arm} populated topology")
    observed = populated(native(RUN / f"{arm}-roundtrip-raw.json"))
    check(all(observed.get(name) == data for name, data in populated(source).items()), f"{arm} populated-cell roundtrip")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "126"], f"{arm} warnings")
    logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    reports[arm] = native(RUN / f"{arm}-report-raw.json")
    for aircraft in (0, 1):
        check(f"Time: 24  system PM task {aircraft} on <TEACH-AIR-01,{aircraft}> PMID: CAL24" in logs[arm], f"{arm} h24 task {aircraft}")
    check(not any("starts performing" in line and "within system PM task" in line and float(line.split()[1]) < 24.25 for line in logs[arm].splitlines()), f"{arm} no early physical PM")
    for name in ("SystemResults", "StockTotalResults"):
        rows = report_rows(reports[arm], name)
        check(len(rows) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rows)), f"{arm} {name} bins")
    sys = report_rows(reports[arm], "SystemResults")
    check(all(abs(r["NSYA"] + r["NSYUA"] - 2) < 0.00001 for r in sys), f"{arm} aircraft conservation")
    check(all(r["NSYA"] == 2 for r in sys[-4:]), f"{arm} terminal ready")
    check(sum(r["NPMS"] for r in sys) == sum(r["NPMT"] for r in sys) == 2, f"{arm} PM starts and completions")
    check(abs(sum(r["NSYPM"] * 0.5 for r in sys) - 2) < 0.00001, f"{arm} two PM hours")
    check("Time: 32 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting" in logs[arm] and
          "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success" in logs[arm], f"{arm} third mission")

for arm, second_start, second_end in (("rise", 24.75, 25.75), ("hold", 25.25, 26.25)):
    for aircraft, start, end in ((0, 24.25, 25.25), (1, second_start, second_end)):
        sub = f"subtask {aircraft} seqno 1 within system PM task {aircraft} on <TEACH-AIR-01,{aircraft}>"
        check(f"Time: {start}  {sub} starts performing, planned to last for 1 hours" in logs[arm], f"{arm} PM start {aircraft}")
        check(f"Time: {end}  {sub} completed" in logs[arm], f"{arm} PM end {aircraft}")
rise_rows = report_rows(reports["rise"], "SystemResults")
hold_rows = report_rows(reports["hold"], "SystemResults")
for i, expected_rise, expected_hold in ((48, 0.5, 0.5), (49, 1.5, 1), (50, 1.5, 1), (51, 0.5, 1), (52, 0, 0.5)):
    check(rise_rows[i]["NSYPM"] == expected_rise and hold_rows[i]["NSYPM"] == expected_hold, f"PM bin {i}")
check(report_rows(reports["rise"], "ResultSummary") == report_rows(reports["hold"], "ResultSummary"), "mission summary equal")
check(report_rows(reports["rise"], "StockTotalResults") == report_rows(reports["hold"], "StockTotalResults"), "stock trace equal")

verdict = {
    "schema": "simlox-d13-dynamic-maxpm-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failed), "checks_total": checks, "passed": not failed, "failures": failed,
    "observed": "Both CAL24 PM objects start h24. Capacity0 postpones physical work until h24.25; one aircraft starts then. Capacity2 from h24.75 starts the second before the first completes, while capacity1 control waits until h25.25.",
    "limits": "One seed, two aircraft, one local PM, three nonoverlapping explicit capacity periods. No internal counter, overlap-error, repeated/nested profile or general boundary law claim.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for reason in failed:
    print(reason)
raise SystemExit(0 if verdict["passed"] else 1)
