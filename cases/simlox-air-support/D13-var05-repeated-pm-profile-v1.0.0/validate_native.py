"""Read-only author replay of sealed D13 repeated/nested PM profile evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d13-repeated-pm-profile-v100-ssh-20261004-01"
PARENT = HERE.parent / "D13-var01-pm-activation-v1.0.0"
PARENT_RUN = PARENT / "runs/d13-var01-activation-v100-ssh-20260930-01"
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


def report_table(doc, name):
    return next(t for t in doc["report"]["tables"] if t["name"] == name)


def report_rows(doc, name):
    t = report_table(doc, name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for i in t["instances"] for row in i["rows"]]


contract = load(HERE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
outcome = load(RUN / "outcome.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "D13" and contract["variant_ids"] == ["D13.var05"], "contract identity")
check(contract["run_id"] == RUN.name == closure["run_id"] == invocation["run_id"], "run identity")
check(closure["error"] is None and outcome["error"] is None, "successful closure")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
paths = {
    "contract": HERE / "contract.json",
    "flat": HERE / "flat-input.json",
    "nested": HERE / "nested-input.json",
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
check([s["name"] for s in steps] == [f"{a}_{stage}" for a in ("flat", "nested") for stage in ("import", "export", "calc", "report")], "step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")

inputs = {a: load(HERE / f"{a}-input.json") for a in ("flat", "nested")}
parent = load(PARENT / "native-input.json")
for arm, count, profile in (("flat", 32, "PM-FLAT"), ("nested", 25, "PM-ROOT")):
    source = inputs[arm]
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm] == sha(RUN / f"{arm}-input.json"), f"{arm} input seal")
    check(len(source["model"]["tables"]) == len(parent["model"]["tables"]) == 33, f"{arm} table topology")
    for source_table, parent_table in zip(source["model"]["tables"], parent["model"]["tables"]):
        if source_table["name"] not in ("ProblemDescription", "PMActivation", "PMActivationProfile"):
            check(source_table == parent_table, f"{arm} fixed parent table {source_table['name']}")
    activation = table(source, "PMActivation")
    columns = [c["name"] for c in activation["columns"]]
    check(activation["instances"][0]["rows"][0][columns.index("PRID")] == profile, f"{arm} selected profile")
    authored = populated(source)
    check(len(authored) == 20 and sum(len(t["rows"]) for t in authored.values()) == count, f"{arm} populated topology")
    observed = populated(native(RUN / f"{arm}-roundtrip-raw.json"))
    check(all(observed.get(name) == data for name, data in authored.items()), f"{arm} populated roundtrip")
    check(outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 2, 0], f"{arm} converter")
    check((RUN / f"{arm}.sxo").stat().st_size > 1000, f"{arm} SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    check(re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "126"], f"{arm} warnings")

flat_rows = table(inputs["flat"], "PMActivationProfile")["instances"][0]["rows"]
nested_rows = table(inputs["nested"], "PMActivationProfile")["instances"][0]["rows"]
expected_flat = [["PM-FLAT", "<LIMIT>", float(cycle * 12 + offset), float(cycle * 12 + offset + 6), 1, 0.0, enabled, "Y", None]
                 for cycle in range(5) for offset, enabled in ((0, "N"), (6, "Y"))]
expected_nested = [["PM-ROOT", "PM-HALF", 0.0, None, 5, 12.0, None, None, None],
                   ["PM-HALF", "<LIMIT>", 0.0, 6.0, 1, 0.0, "N", "Y", None],
                   ["PM-HALF", "<LIMIT>", 6.0, 12.0, 1, 0.0, "Y", "Y", None]]
check(flat_rows == expected_flat, "flat five-cycle schedule")
check(nested_rows == expected_nested, "nested repeat source")
expanded_nested = []
for cycle in range(nested_rows[0][4]):
    base = nested_rows[0][2] + cycle * nested_rows[0][5]
    for child in nested_rows[1:]:
        expanded_nested.append((base + child[2], base + child[3], child[6], child[7]))
check(expanded_nested == [(r[2], r[3], r[6], r[7]) for r in flat_rows], "expanded profile equality")

flat_log = (RUN / "flat.log").read_bytes()
nested_log = (RUN / "nested.log").read_bytes()
check(flat_log == nested_log, "paired event-log byte parity")
check(flat_log == (PARENT_RUN / "model.log").read_bytes(), "accepted parent event-log parity")
events = flat_log.decode("utf-8-sig")
for start, end, task in ((30, 31, 0), (55, 56, 1)):
    sub = f"subtask {task} seqno 1 within system PM task {task} on <TEACH-AIR-01,0>"
    check(f"Time: {start}  {sub} starts performing, planned to last for 1 hours" in events, f"PM work start {task}")
    check(f"Time: {end}  {sub} completed" in events, f"PM work complete {task}")
check("Time: 24  system PM task" not in events, "no h24 PM object")
for start, end in ((8, 10), (20, 22), (32, 34)):
    check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT" in events and f"Time: {end} <BASIC-MISSION,TEACH-UNIT" in events, f"mission {start}-{end}")

reports = {a: native(RUN / f"{a}-report-raw.json") for a in ("flat", "nested")}
parent_report = native(PARENT_RUN / "report-raw.json")
for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
    check(report_table(reports["flat"], name) == report_table(reports["nested"], name) == report_table(parent_report, name), f"{name} flat/nested/parent parity")
for arm in ("flat", "nested"):
    for name in ("SystemResults", "StockTotalResults"):
        rows = report_rows(reports[arm], name)
        check(len(rows) == 120 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rows)), f"{arm} {name} bins")
    sys = report_rows(reports[arm], "SystemResults")
    check(sum(r["NPMS"] for r in sys) == sum(r["NPMT"] for r in sys) == 2, f"{arm} PM starts/completions")
    check(abs(sum(r["NSYPM"] * 0.5 for r in sys) - 2) < 0.00001, f"{arm} PM occupancy")
    check(abs(sum(r["NSYMO"] * 0.5 for r in sys) - 6) < 0.00001, f"{arm} mission occupancy")
    check(all(abs(r["NSYA"] + r["NSYUA"] - 1) < 0.00001 for r in sys), f"{arm} aircraft conservation")
    check(sys[-1]["NSYA"] == 1, f"{arm} terminal ready")

verdict = {
    "schema": "simlox-d13-repeated-pm-profile-author-readonly-validation/v1",
    "run_id": RUN.name, "closure_sha256": sha(RUN / "closure.json"),
    "checks_passed": checks - len(failed), "checks_total": checks, "passed": not failed, "failures": failed,
    "observed": "Five nested 12-hour PM activation cycles expand to the flat ten-period schedule. Native flat/nested event logs are byte-identical to each other and accepted D13.var01; non-description report tables match, with PM work h30-31 and h55-56.",
    "limits": "One seed, one aircraft and one PM; no internal counter, other cycle/depth, overlapping-limit, global ENPM, GUI or general hierarchy claim.",
}
(HERE / "author-native-validation-2026-10-04.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{'GO' if verdict['passed'] else 'NO-GO'}: {verdict['checks_passed']}/{checks}")
for reason in failed:
    print(reason)
raise SystemExit(0 if verdict["passed"] else 1)
