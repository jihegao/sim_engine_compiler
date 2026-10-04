"""Independent standard-library replay of sealed D13.var02/04 native evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN = CASE / "runs" / "d13-crit-capacity-v100-ssh-20261004-01"
OUT = CASE / "review" / "independent-verdict.json"
checks, failures = 0, []


def ck(test, label):
    global checks
    checks += 1
    if not test:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
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
            out.append(ch)
            quoted = True
        elif ch == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in ']}':
                out.append(ch)
        else:
            out.append(ch)
    return json.loads(''.join(out))


def tables(doc, key="model"):
    return {table["name"]: table for table in doc[key]["tables"]}


def records(table):
    cols = [col["name"] for col in table["columns"]]
    return [(instance["instance_name"], dict(zip(cols, row)))
            for instance in table["instances"] for row in instance["rows"]]


def result_rows(report, name):
    table = tables(report, "report")[name]
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def near(a, b, tol=4e-4):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def overlap(a, b, c, d):
    return max(0., min(b, d) - max(a, c))


contract, closure = load(CASE / "contract.json"), load(RUN / "closure.json")
invocation, steps = load(RUN / "invocation.json"), load(RUN / "steps.json")
ck(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "sealed run identity")
ck(sha(CASE / "contract.json") == "8799817ebb70b42eb33eec1cffcc3c3cb3d807c57e860405dd8785d175055411", "pre-run contract hash")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["error"] is None and closure["publication_state"] == "not_published", "successful unpublished closure")
ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH ancestry")
ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue mutex")
ck(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "preserved GUI identity")
ck(len(steps) == 8, "eight native steps")
for arm in ("y", "n"):
    for phase in ("import", "export", "calc", "report"):
        step = next((item for item in steps if item["name"] == f"{arm}_{phase}"), None)
        ck(step is not None and step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {phase} guarded completion")
        if phase == "calc" and step:
            ck("-threads 1" in step["arguments"], f"{arm} serial calculation")

parent_package = ROOT / contract["dependency"]["parent_package"]
activation_package = ROOT / contract["dependency"]["activation_template_package"]
paths = {
    "contract": CASE / "contract.json", "y": CASE / "y-input.json", "n": CASE / "n-input.json",
    "parent_input": parent_package / "native-input.json",
    "parent_closure": parent_package / "runs" / "d13-maxpm-two-v100-ssh-20260930-01" / "closure.json",
    "parent_signoff": parent_package / "cli-scope-signoff-2026-09-30.md",
    "activation_input": activation_package / "native-input.json",
    "activation_closure": activation_package / "runs" / "d13-var01-activation-v100-ssh-20260930-01" / "closure.json",
    "activation_signoff": activation_package / "cli-scope-signoff-2026-09-30.md",
    "build.py": CASE / "build.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key, digest in sorted(closure["source_hashes_before"].items()):
    ck(digest == closure["source_hashes_after"].get(key) == invocation["source_hashes_before"].get(key), f"stable source seal {key}")
    if key in paths:
        ck(paths[key].is_file() and sha(paths[key]) == digest, f"disk source seal {key}")
for key, source_key in (("y", "y"), ("n", "n")):
    ck(closure["source_hashes_before"][key] == contract["inputs_sha256"][source_key], f"{key} contract source pin")
for key, contract_key in (("parent_input", "parent_input_sha256"), ("parent_closure", "parent_closure_sha256"), ("parent_signoff", "parent_signoff_sha256"), ("activation_input", "activation_input_sha256"), ("activation_closure", "activation_closure_sha256"), ("activation_signoff", "activation_signoff_sha256")):
    ck(closure["source_hashes_before"][key] == contract["dependency"][contract_key], f"{key} dependency pin")
ck(closure["source_hashes_before"]["manual"] == contract["manual"]["sha256"], "installed manual pin")
ck(len(closure["raw"]) == 22, "22 raw SHA seals")
for name, seal in sorted(closure["raw"].items()):
    file = RUN / name
    ck(file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"], f"raw SHA and size {name}")

parent = tables(load(paths["parent_input"]))
activation = tables(load(paths["activation_input"]))
source = {arm: tables(load(CASE / f"{arm}-input.json")) for arm in ("y", "n")}
ck(set(parent) | {"PMActivation"} == set(source["y"]) == set(source["n"]), "parent plus activation table topology")
ck({name for name in parent if parent[name] != source["y"][name]} == {"ProblemDescription", "Unit", "MaterielPM"}, "parent-to-Y existing-table changes")
ck({name for name in source["y"] if source["y"][name] != source["n"][name]} == {"ProblemDescription", "PMActivation"}, "pair only description and CRIT")
ck([c["name"] for c in source["y"]["PMActivation"]["columns"]] == [c["name"] for c in activation["PMActivation"]["columns"]], "accepted activation schema")
for arm, flag in (("y", "Y"), ("n", "N")):
    units = [row for _, row in records(source[arm]["Unit"]) if row.get("UNID") == "TEACH-UNIT"]
    ck(len(units) == 1 and units[0].get("MAXPM") == 0, f"{arm} zero capacity")
    pm = [row for _, row in records(source[arm]["MaterielPM"]) if row.get("PMID") == "CAL24"]
    ck(len(pm) == 1 and near(pm[0]["PMINT"], 24) and near(pm[0]["DTIM"], .1), f"{arm} PM interval and tolerance")
    rule = [row for _, row in records(source[arm]["PMActivation"]) if row.get("PMID") == "CAL24"]
    ck(len(rule) == 1 and rule[0]["USTID"] == "TEACH-UNIT" and rule[0]["ENPM"] == "Y" and rule[0]["CRIT"] == flag, f"{arm} activation flag")
    ck(all(row.get("CRIT") == flag for _, row in records(source[arm]["PMActivation"]) if row.get("PMID") == "CAL24"), f"{arm} isolated CRIT value")

observed = {}
for arm in ("y", "n"):
    authored, exported = source[arm], tables(load(RUN / f"{arm}-roundtrip-raw.json"))
    ck(set(authored) == set(exported), f"{arm} export table topology")
    for name, table in sorted(authored.items()):
        actual = records(exported[name])
        for instance, row in records(table):
            if any(value is not None for value in row.values()):
                ck(any(i == instance and all(r.get(k) == v for k, v in row.items()) for i, r in actual), f"{arm} authored populated cells {name}/{instance}/{row}")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} zero converter errors")
    ck("(warning #108)" in runlog and "(warning #126)" in runlog, f"{arm} exact warning classes")
    ck((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} usable SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    report = load(RUN / f"{arm}-report-raw.json")
    system, stock, summary = (result_rows(report, name) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck(len(system) == len(stock) == 72 and len(summary) == 1, f"{arm} 72 half-hour bins")
    for index, (sys, stk) in enumerate(zip(system, stock)):
        for row, name in ((sys, "System"), (stk, "Stock")):
            ck(near(row["STINT"], index / 2) and near(row["ETINT"], (index + 1) / 2), f"{arm} {name} bin {index}")
        ck(near(sys["NSYA"] + sys["NSYUA"], 2), f"{arm} aircraft conservation bin {index}")
        ck(all(stk[key] is None or near(stk[key], 0) for key in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP")), f"{arm} zero stock demand bin {index}")
        left, right = index / 2, (index + 1) / 2
        expected_pm = 2 * overlap(26.4, 27.4, left, right) / .5 if arm == "y" else 0
        ck(near(sys["NSYPM"], expected_pm), f"{arm} event-derived physical PM bin {index}")
        ck(near(sys["NPMS"], 2 if index == 48 else 0), f"{arm} h24 PM task start marker bin {index}")
        ck(near(sys["NPMT"], 2 if arm == "y" and index == 54 else 0), f"{arm} PM completion marker bin {index}")
    ck(near(sum(float(row["NSYPM"]) * .5 for row in system), 2 if arm == "y" else 0), f"{arm} integrated physical PM hours")
    ck(near(system[-1]["NSYRY"], 2) and near(system[-1]["NSYA"], 2), f"{arm} terminal ready two")
    ck(near(summary[0]["NREP"], 1) and near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 1), f"{arm} successful mission summary")
    for index, (start, end) in enumerate(((8, 10), (20, 22), (32, 34))):
        identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>"
        ck(f"Time: {start} {identity} mission starting" in log and f"Time: {end} {identity} mission success" in log, f"{arm} mission {index} identity/outcome")
    for task in (0, 1):
        ck(bool(re.search(rf"Time: 24  system PM task {task} on <TEACH-AIR-01,[01]> started", log)), f"{arm} task object {task} at 24")
        ck(bool(re.search(rf"Time: 24  system PM task {task} on <TEACH-AIR-01,[01]> PMID: CAL24", log)), f"{arm} task {task} PM identity")
    observed[arm] = (log, system, stock, summary)

ylog, ysystem, ystock, ysummary = observed["y"]
nlog, nsystem, nstock, nsummary = observed["n"]
for task in (0, 1):
    ck(bool(re.search(rf"Time: 26\.4  system PM task {task} on <TEACH-AIR-01,[01]> reactivated", ylog)), f"Y task {task} reactivated")
    ck(bool(re.search(rf"Time: 26\.4  subtask {task} seqno 1 .* starts performing", ylog)), f"Y task {task} physical work starts")
    ck(bool(re.search(rf"Time: 27\.4  system PM task {task} on <TEACH-AIR-01,[01]> completed", ylog)), f"Y task {task} completes")
ck(not re.search(r"starts performing|system PM task [01].* completed", nlog), "N no physical PM through horizon")
ck("Time: 31 <TEACH-AIR-01,BASE-01,0> system PM task 0 on <TEACH-AIR-01,0> paused." in nlog, "N pending task paused for third mission")
ck("Time: 34 <TEACH-AIR-01,BASE-01,0> system PM task 0 on <TEACH-AIR-01,0> continued" in nlog, "N pending task continued after return")
ck(ystock == nstock and ysummary == nsummary, "stock and mission summary parity")
ck(near(sum(float(row["NSYMO"]) * .5 for row in ysystem), 6) and near(sum(float(row["NSYMO"]) * .5 for row in nsystem), 6), "both three two-hour flights")

verdict = {
    "case": "D13.var02/04 v1.0.0", "run_id": RUN.name,
    "passed": not failures,
    "verdict": "GO — bounded local CRIT Y/N capacity contrast" if not failures else "NO-GO",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "observed": {"both": "CAL24 task objects 0/1 created at h24, MAXPM=0, three missions succeed at h10/22/34.", "CRIT_Y": "Two physical PM subtasks work h26.4–27.4 and complete despite MAXPM=0.", "CRIT_N": "No physical PM through h36; one pending task pauses for the third mission and continues after h34 return.", "terminal": "Two aircraft ready at h36 in both arms."},
    "limits": ["One seed, two aircraft, one PM type and fixed MAXPM=0; no general capacity law.", "Task creation at h24 is distinct from physical work; hidden PM counter state is not observed.", "CRIT=N noncritical state after h34 is inferred from source setting and continued pending task, not a directly printed status field."],
    "sha256": {"contract": sha(CASE / "contract.json"), "closure": sha(RUN / "closure.json"), "y_report": sha(RUN / "y-report-raw.json"), "n_report": sha(RUN / "n-report-raw.json")},
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{verdict['verdict']}: {verdict['checks_passed']}/{verdict['checks_total']}")
for failure in failures[:25]:
    print("FAIL", failure)
