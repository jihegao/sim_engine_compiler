"""Read-only author replay of sealed D13 CRIT/MAXPM native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d13-crit-capacity-v100-ssh-20261004-01"
PARENT = HERE.parent / "D13-var02-maxpm-two-v1.0.0"
PARENT_RUN = PARENT / "runs/d13-maxpm-two-v100-ssh-20260930-01"
ACTIVATION = HERE.parent / "D13-var01-pm-activation-v1.0.0"
ACTIVATION_RUN = ACTIVATION / "runs/d13-var01-activation-v100-ssh-20260930-01"
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
    result = {}
    for t in doc["model"]["tables"]:
        rows = [r for instance in t["instances"] for r in instance["rows"]]
        if rows:
            result[t["name"]] = {"columns": t["columns"], "rows": rows}
    return result


def report_rows(report, name):
    t = next(t for t in report["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row)) for instance in t["instances"] for row in instance["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D13" and contract["variant_ids"] == ["D13.var02", "D13.var04"], "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json",
    "y": HERE / "y-input.json",
    "n": HERE / "n-input.json",
    "parent_input": PARENT / "native-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "activation_input": ACTIVATION / "native-input.json",
    "activation_closure": ACTIVATION_RUN / "closure.json",
    "activation_signoff": ACTIVATION / "cli-scope-signoff-2026-09-30.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": HERE / "build.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
check(set(paths) == set(closure["source_hashes_before"]), "source inventory")
for key, path in paths.items():
    check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source seal {key}")
for key in ("parent_input", "parent_closure", "parent_signoff", "activation_input", "activation_closure", "activation_signoff"):
    check(closure["source_hashes_before"][key] == contract["dependency"][key + "_sha256"], f"contract dependency {key}")
check(len(closure["raw"]) == 22, "raw inventory count")
for name, item in closure["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI")
check([s["name"] for s in steps] == [f"{a}_{stage}" for a in ("y", "n") for stage in ("import", "export", "calc", "report")], "step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {a: load(HERE / f"{a}-input.json") for a in ("y", "n")}
diff = []
for yt, nt in zip(inputs["y"]["model"]["tables"], inputs["n"]["model"]["tables"]):
    assert yt["name"] == nt["name"] and yt["columns"] == nt["columns"]
    for yi, ni in zip(yt["instances"], nt["instances"]):
        for yr, nr in zip(yi["rows"], ni["rows"]):
            for col, yv, nv in zip(yt["columns"], yr, nr):
                if yv != nv:
                    diff.append((yt["name"], col["name"], yv, nv))
check(diff == [("ProblemDescription", "PDESC", "D13.var02/04 CRIT=Y at MAXPM=0", "D13.var02/04 CRIT=N at MAXPM=0"), ("PMActivation", "CRIT", "Y", "N")], "pair-only CRIT difference")
for arm in ("y", "n"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input seal/copy")
    ctl = table(inputs[arm], "Control")
    names = [c["name"] for c in ctl["columns"]]
    check(ctl["instances"][0]["rows"][0][names.index("ENPM")] == "Y", f"{arm} global PM enabled")
    unit = table(inputs[arm], "Unit")
    names = [c["name"] for c in unit["columns"]]
    check(unit["instances"][0]["rows"][0][names.index("MAXPM")] == 0, f"{arm} MAXPM zero")
    exported = native(RUN / f"{arm}-roundtrip-raw.json")
    authored = populated(inputs[arm])
    observed = populated(exported)
    check(len(authored) == 19 and sum(len(t["rows"]) for t in authored.values()) == 22, f"{arm} populated topology")
    check(all(observed.get(name) == data for name, data in authored.items()), f"{arm} populated-cell roundtrip")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0], f"{arm} converter outcome")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} usable SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "126"], f"{arm} warning classification")

logs = {a: (RUN / f"{a}.log").read_text(encoding="utf-8-sig") for a in ("y", "n")}
reports = {a: native(RUN / f"{a}-report-raw.json") for a in ("y", "n")}
for arm in ("y", "n"):
    for aircraft in (0, 1):
        small = f"system PM task {aircraft} on <TEACH-AIR-01,{aircraft}>"
        check(f"Time: 24  {small} PMID: CAL24" in logs[arm], f"{arm} PM object aircraft {aircraft}")
    check("critical random failure added" not in logs[arm], f"{arm} no fault confound")
    for name in ("SystemResults", "StockTotalResults"):
        rs = report_rows(reports[arm], name)
        check(len(rs) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rs)), f"{arm} {name} 72 bins")
    sys = report_rows(reports[arm], "SystemResults")
    check(all(abs(r["NSYA"] + r["NSYUA"] - 2) < 0.00001 for r in sys), f"{arm} aircraft conservation")
    check(all(r["NSYA"] == 2 for r in sys[-4:]), f"{arm} terminal two ready")
    check("Time: 32 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting" in logs[arm] and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success" in logs[arm], f"{arm} third mission")

for aircraft in (0, 1):
    sub = f"subtask {aircraft} seqno 1 within system PM task {aircraft} on <TEACH-AIR-01,{aircraft}>"
    check(f"Time: 26.4  {sub} starts performing, planned to last for 1 hours" in logs["y"], f"Y physical PM aircraft {aircraft}")
    check(f"Time: 27.4  {sub} completed" in logs["y"], f"Y PM complete aircraft {aircraft}")
check(not any("within system PM task" in line and "starts performing" in line for line in logs["n"].splitlines()), "N no physical PM")
check("Time: 31 <TEACH-AIR-01,BASE-01,0> system PM task 0 on <TEACH-AIR-01,0> paused." in logs["n"], "N pending PM pauses for mission")
check(bool(re.search(r"Time: 34 <TEACH-AIR-01,BASE-01,0> System arrives[^\n]*\n\s*no failures\s*\n\s*1 PM tasks:\s*\n\s*\.CAL24 Non-Critical", logs["n"])), "N remains noncritical at h34 return")
for arm, hours, complete in (("y", 2, 2), ("n", 0, 0)):
    sys = report_rows(reports[arm], "SystemResults")
    check(sum(r["NPMS"] for r in sys) == 2 and sum(r["NPMT"] for r in sys) == complete, f"{arm} PM starts/completions")
    check(abs(sum(r["NSYPM"] * 0.5 for r in sys) - hours) < 0.0001, f"{arm} PM occupancy")
check(report_rows(reports["y"], "ResultSummary") == report_rows(reports["n"], "ResultSummary"), "same mission summary")
check(report_rows(reports["y"], "StockTotalResults") == report_rows(reports["n"], "StockTotalResults"), "same stock trace")

verdict = {
    "schema": "simlox-d13-crit-capacity-author-readonly-validation/v1",
    "run_id": RUN.name,
    "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failed),
    "checks_total": checks,
    "passed": not failed,
    "failures": failed,
    "observed": "Both arms create two CAL24 PM task objects at h24. With CRIT=Y, both work h26.4-27.4 despite MAXPM=0; with CRIT=N, neither physically works through h36 and a pending CAL24 is logged noncritical after the h32-34 mission.",
    "limits": "One seed, two aircraft, MAXPM=0, one local PM; no direct internal counter values, Control.ENPM=N or time-varying capacity comparison.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for reason in failed:
    print(reason)
raise SystemExit(0 if verdict["passed"] else 1)
