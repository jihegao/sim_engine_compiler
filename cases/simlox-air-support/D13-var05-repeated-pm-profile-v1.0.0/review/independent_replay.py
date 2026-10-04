"""Independent read-only replay of sealed D13.var05 flat/nested PM profiles."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN = CASE / "runs" / "d13-repeated-pm-profile-v100-ssh-20261004-01"
OUT = CASE / "review" / "independent-verdict.json"
checks, failures = 0, []


def ck(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_text(encoding="utf-8-sig")
    out, quoted, escaped = [], False, False
    for i, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in ']}':
                out.append(ch)
        else:
            out.append(ch)
    return json.loads(''.join(out))


def tables(document, root="model"):
    return {t["name"]: t for t in document[root]["tables"]}


def records(table):
    columns = [col["name"] for col in table["columns"]]
    return [(ins["instance_name"], dict(zip(columns, row))) for ins in table["instances"] for row in ins["rows"]]


def rows(report, table_name):
    table = tables(report, "report")[table_name]
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for ins in table["instances"] for row in ins["rows"]]


def near(a, b, tolerance=3e-4):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance)


def overlap(a, b, c, d):
    return max(0., min(b, d) - max(a, c))


contract, closure = read(CASE / "contract.json"), read(RUN / "closure.json")
inv, steps = read(RUN / "invocation.json"), read(RUN / "steps.json")
ck(contract["run_id"] == closure["run_id"] == inv["run_id"] == RUN.name, "run identity")
ck(sha(CASE / "contract.json") == "91133abd1a1194b39994f60d6363a33ce3080e647ee30bff502d4879f1ad1b4f", "pre-run contract")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["error"] is None and closure["publication_state"] == "not_published", "closure status")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-zero SSH")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "queue mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
ck(len(steps) == 8, "eight guarded native steps")
for arm in ("flat", "nested"):
    for action in ("import", "export", "calc", "report"):
        step = next((s for s in steps if s["name"] == f"{arm}_{action}"), None)
        ck(step is not None and step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {action} completed")
        if action == "calc" and step:
            ck("-threads 1" in step["arguments"], f"{arm} serial calc")

parent_pkg = ROOT / contract["dependency"]["parent_package"]
parent_run = parent_pkg / "runs" / "d13-var01-activation-v100-ssh-20260930-01"
paths = {
    "contract": CASE / "contract.json", "flat": CASE / "flat-input.json", "nested": CASE / "nested-input.json",
    "parent_input": parent_pkg / "native-input.json", "parent_closure": parent_run / "closure.json",
    "parent_signoff": parent_pkg / "cli-scope-signoff-2026-09-30.md",
    "build.py": CASE / "build.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key, digest in sorted(closure["source_hashes_before"].items()):
    ck(digest == closure["source_hashes_after"].get(key) == inv["source_hashes_before"].get(key), f"source stable {key}")
    if key in paths:
        ck(paths[key].is_file() and sha(paths[key]) == digest, f"source disk hash {key}")
for arm in ("flat", "nested"):
    ck(closure["source_hashes_before"][arm] == contract["inputs_sha256"][arm], f"{arm} contract input pin")
for key in ("parent_input", "parent_closure", "parent_signoff"):
    ck(closure["source_hashes_before"][key] == contract["dependency"][key + "_sha256"], f"parent contract pin {key}")
ck(closure["source_hashes_before"]["manual"] == contract["manual"]["sha256"], "manual pin")
ck(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in sorted(closure["raw"].items()):
    file = RUN / name
    ck(file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"], f"raw seal {name}")

parent = tables(read(paths["parent_input"]))
source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in ("flat", "nested")}
ck(set(parent) == set(source["flat"]) == set(source["nested"]), "table names unchanged")
ck({name for name in parent if parent[name] != source["flat"][name]} == {"ProblemDescription", "PMActivation", "PMActivationProfile"}, "parent-to-flat table delta")
ck({name for name in source["flat"] if source["flat"][name] != source["nested"][name]} == {"ProblemDescription", "PMActivation", "PMActivationProfile"}, "paired table delta")
for arm, profile_name in (("flat", "PM-FLAT"), ("nested", "PM-ROOT")):
    activation = [row for _, row in records(source[arm]["PMActivation"]) if row.get("PMID") == "CAL24"]
    ck(len(activation) == 1 and activation[0]["PRID"] == profile_name, f"{arm} activation profile binding")
flat = [row for _, row in records(source["flat"]["PMActivationProfile"]) if row.get("PRID") == "PM-FLAT"]
ck(len(flat) == 10, "flat ten authored periods")
for i, row in enumerate(flat):
    ck(row["SPRID"] == "<LIMIT>" and row["STIM"] == 6*i and row["ETIM"] == 6*(i+1) and row["IQTY"] == 1 and row["IINT"] == 0 and row["ENPM"] == ("N" if i % 2 == 0 else "Y"), f"flat period {i}")
nested = [row for _, row in records(source["nested"]["PMActivationProfile"]) if row.get("PRID") in ("PM-ROOT", "PM-HALF")]
ck(len(nested) == 3, "three nested authored rows")
root = [row for row in nested if row["PRID"] == "PM-ROOT"]
half = [row for row in nested if row["PRID"] == "PM-HALF"]
ck(len(root) == 1 and root[0]["SPRID"] == "PM-HALF" and root[0]["STIM"] == 0 and root[0]["IQTY"] == 5 and root[0]["IINT"] == 12, "root repeated child reference")
ck(len(half) == 2 and [(r["SPRID"],r["STIM"],r["ETIM"],r["ENPM"]) for r in half] == [("<LIMIT>",0,6,"N"),("<LIMIT>",6,12,"Y")], "child two adjacent periods")
expanded = [(12*k + row["STIM"], 12*k + row["ETIM"], row["ENPM"]) for k in range(5) for row in half]
ck(expanded == [(row["STIM"],row["ETIM"],row["ENPM"]) for row in flat], "source-derived five-cycle expansion equals flat source")

observed = {}
for arm in ("flat", "nested"):
    authored, exported = source[arm], tables(read(RUN / f"{arm}-roundtrip-raw.json"))
    ck(set(authored) == set(exported), f"{arm} native table set")
    for name, table in sorted(authored.items()):
        actual = records(exported[name])
        for instance, row in records(table):
            if any(value is not None for value in row.values()):
                ck(any(i == instance and all(got.get(col) == val for col, val in row.items()) for i, got in actual), f"{arm} populated cells {name}/{instance}/{row}")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} zero converter errors")
    ck("(warning #108)" in runlog and "(warning #126)" in runlog, f"{arm} warnings 108/126")
    ck((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} usable SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    report = read(RUN / f"{arm}-report-raw.json")
    system, stock, summary = (rows(report, table_name) for table_name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck(len(system) == len(stock) == 120 and len(summary) == 1, f"{arm} report dimensions")
    for index, (sys, stk) in enumerate(zip(system, stock)):
        for row, label in ((sys, "system"), (stk, "stock")):
            ck(near(row["STINT"], index / 2) and near(row["ETINT"], (index + 1) / 2), f"{arm} {label} bin {index}")
        ck(near(sys["NSYA"] + sys["NSYUA"], 1), f"{arm} aircraft conservation bin {index}")
        ck(all(stk[key] is None or near(stk[key], 0) for key in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP")), f"{arm} no stock demand bin {index}")
        left, right = index / 2, (index + 1) / 2
        expected_pm = (overlap(30, 31, left, right) + overlap(55, 56, left, right)) / .5
        ck(near(sys["NSYPM"], expected_pm), f"{arm} event-derived PM bin {index}")
        ck(near(sys["NPMS"], 1 if index in (60,110) else 0), f"{arm} PM start marker bin {index}")
        ck(near(sys["NPMT"], 1 if index in (62,112) else 0), f"{arm} PM completion marker bin {index}")
    ck(near(sum(float(r["NSYPM"]) * .5 for r in system), 2), f"{arm} two PM work hours")
    ck(near(sum(float(r["NSYMO"]) * .5 for r in system), 6), f"{arm} six flight hours")
    ck(near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYA"], 1), f"{arm} terminal aircraft ready")
    ck(near(summary[0]["NREP"], 1) and near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 1), f"{arm} successful mission summary")
    for mission, (start, end) in enumerate(((8,10),(20,22),(32,34))):
        identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
        ck(f"Time: {start} {identity} mission starting" in log and f"Time: {end} {identity} mission success" in log, f"{arm} mission {mission}")
    for task, (start, end) in enumerate(((30,31),(55,56))):
        ck(f"Time: {start}  system PM task {task} on <TEACH-AIR-01,0> started" in log, f"{arm} PM task {task} start")
        ck(f"Time: {start}  system PM task {task} on <TEACH-AIR-01,0> PMID: CAL24" in log, f"{arm} PM task {task} identity")
        ck(bool(re.search(rf"Time: {start}  subtask {task} seqno 1 .* starts performing", log)), f"{arm} PM task {task} work")
        ck(f"Time: {end}  system PM task {task} on <TEACH-AIR-01,0> completed" in log, f"{arm} PM task {task} end")
    observed[arm] = (system, stock, summary)

ck(sha(RUN / "flat.log") == sha(RUN / "nested.log"), "flat/nested byte-identical native event log")
ck(sha(RUN / "flat.log") == sha(parent_run / "model.log"), "accepted parent event-log parity")
ck(observed["flat"] == observed["nested"], "all non-description report rows equal")
parent_report = read(parent_run / "report-raw.json")
for name, arm_rows in (("SystemResults",observed["flat"][0]),("StockTotalResults",observed["flat"][1]),("ResultSummary",observed["flat"][2])):
    ck(rows(parent_report, name) == arm_rows, f"accepted parent report parity {name}")

verdict = {
    "case": "D13.var05 v1.0.0", "run_id": RUN.name,
    "passed": not failures, "verdict": "GO — bounded flat/nested five-cycle equivalence" if not failures else "NO-GO",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "observed": {"source": "Ten flat six-hour N/Y periods equal five repetitions of the nested PM-ROOT to PM-HALF 12-hour block.", "native": "Flat, nested and accepted parent event logs are byte-identical; PM works h30–31 and h55–56, and three missions succeed.", "report": "All non-description report rows agree; 120 System/Stock half-hour bins reconcile and one aircraft is ready at h60."},
    "limits": ["One seed, one aircraft, one PM, five repeats of one two-period child; no general nested-profile equivalence law.", "No internal PM counter trace, overlapping-cycle, deeper-nesting, global ENPM, GUI or cross-engine claim."],
    "sha256": {"contract": sha(CASE / "contract.json"), "closure": sha(RUN / "closure.json"), "flat_report": sha(RUN / "flat-report-raw.json"), "nested_report": sha(RUN / "nested-report-raw.json")},
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{verdict['verdict']}: {verdict['checks_passed']}/{verdict['checks_total']}")
for failure in failures[:25]:
    print("FAIL", failure)
