"""Independent read-only replay of the I06 scheduled reliability diagnostic."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "i06-var01-02-reliability-panel-v101-ssh-20261005-01"
ARMS = [f"{kind}-seed{seed}-{arm}" for kind in ("item", "fm") for seed in (1, 2, 3) for arm in ("control", "factor4")]
CHECKS: list[tuple[str, bool]] = []


def check(label: str, result: bool) -> None:
    CHECKS.append((label, bool(result)))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def table_map(doc: dict, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in doc[root]["tables"]}


def records(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")
check("run identity", contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name)
check("closure clean", closure["error"] is None and outcome["error"] is None)
check("invocation SHA", closure["invocation_sha256"] == digest(RUN / "invocation.json"))
check("session zero and SSH ancestry", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
check("native host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("48 ordered CLI steps", [step["name"] for step in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step completed {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)

paths = {
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "item_parent": CASES / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json",
    "fm_parent": CASES / "D02-var02-failure-mode-calendar-v1.0.0" / "native-input.json",
    "diagnostic_closure": CASES / "I06-var01-02-scheduled-reliability-v1.0.0" / "runs" / "i06-var01-02-reliability-panel-v100-ssh-20261005-01" / "closure.json",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for arm in ARMS:
    paths[arm] = CASE / f"{arm}-input.json"
check("complete source set", set(paths) == set(closure["source_hashes_before"]))
for key, before in closure["source_hashes_before"].items():
    check(f"source before/after {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    check(f"source SHA {key}", paths[key].is_file() and digest(paths[key]) == before)
check("parent pins", contract["dependency"]["item_parent_input_sha256"] == closure["source_hashes_before"]["item_parent"] and contract["dependency"]["fm_parent_input_sha256"] == closure["source_hashes_before"]["fm_parent"])
check("excluded diagnostic closure pin", contract["dependency"]["excluded_diagnostic_closure_sha256"] == closure["source_hashes_before"]["diagnostic_closure"])
check("manual pin", contract["manual"]["sha256"] == closure["source_hashes_before"]["manual"])
check("122 raw file seals", len(closure["raw"]) == 122)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw file exists {name}", path.is_file())
    if path.is_file():
        check(f"raw size {name}", path.stat().st_size == seal["bytes"])
        check(f"raw SHA {name}", digest(path) == seal["sha256"])

models = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
diagnostic_case = CASES / "I06-var01-02-scheduled-reliability-v1.0.0"
for arm in ARMS:
    previous = table_map(load(diagnostic_case / f"{arm}-input.json"), "model")
    changed = {name for name in previous if previous[name] != models[arm][name]}
    check(f"v100 to v101 input scope {arm}", changed == ({"OperationProfile"} if arm.startswith("item-") else set()))
    if arm.startswith("item-"):
        old, new = records(previous["OperationProfile"]), records(models[arm]["OperationProfile"])
        check(f"third mission h52 to h23 only {arm}", len(old) == len(new) == 3 and {(i, key) for i, (a, b) in enumerate(zip(old, new)) for key in a if a[key] != b[key]} == {(2, "STIM")} and old[2]["STIM"] == 52 and new[2]["STIM"] == 23)
observed: dict[str, dict] = {}
parent_logs = {
    "item": (CASES / "D02-var01-traditional-op-hours-v1.0.0" / "runs" / "d02-var01-traditional-op-v100-ssh-20260930-01" / "model.log").read_text(encoding="latin-1"),
    "fm": (CASES / "D02-var02-failure-mode-calendar-v1.0.0" / "runs" / "d02-var02-calendar-v100-ssh-20260930-01" / "model.log").read_text(encoding="latin-1"),
}
for kind, parent_log in parent_logs.items():
    check(f"accepted {kind} parent lacks h24 reschedule", not re.search(r"Time: 24 <TEACH-AIR-01,0> Next random failure will occur", parent_log))
for kind in ("item", "fm"):
    change_table = "ChangesItemReliability" if kind == "item" else "ChangesFailureModeReliability"
    change_field = "FRTCF" if kind == "item" else "FRQCF"
    failure_text = "critical random failure added" if kind == "item" else "critical CM failure mode added"
    for seed in (1, 2, 3):
        control, factor = f"{kind}-seed{seed}-control", f"{kind}-seed{seed}-factor4"
        if seed > 1:
            first = f"{kind}-seed1-control"
            check(f"seed-only source delta {kind}/seed{seed}", {name for name in models[first] if models[first][name] != models[control][name]} == {"Control", "ProblemDescription"} and {(i, key) for i, (a, b) in enumerate(zip(records(models[first]["Control"]), records(models[control]["Control"]))) for key in a if a[key] != b[key]} == {(0, "RSEED")})
        check(f"paired table set {kind}/seed{seed}", models[control].keys() == models[factor].keys())
        check(f"paired changed tables {kind}/seed{seed}", {name for name in models[control] if models[control][name] != models[factor][name]} == {"ProblemDescription", change_table})
        crows, frows = records(models[control][change_table]), records(models[factor][change_table])
        check(f"h9/h24 source rows {kind}/seed{seed}", len(crows) == len(frows) == 2 and [r["TIMEC"] for r in crows] == [r["TIMEC"] for r in frows] == [9.0, 24.0])
        check(f"only h9 factor delta {kind}/seed{seed}", {(i, key) for i, (a, b) in enumerate(zip(crows, frows)) for key in a if a[key] != b[key]} == {(0, change_field)} and crows[0][change_field] == 1 and frows[0][change_field] == 4 and crows[1][change_field] == frows[1][change_field] == 1)
        for arm in (control, factor):
            source = models[arm]
            check(f"contract input pin {arm}", contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
            check(f"run-local source copy {arm}", digest(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
            check(f"source seed {arm}", records(source["Control"])[0]["RSEED"] == str(seed))
            check(f"authored table count {arm}", len(source) == (32 if kind == "item" else 36))
            check(f"19 populated tables {arm}", sum(bool(records(table)) for table in source.values()) == 19)
            exported = table_map(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
            for name, table in source.items():
                original = records(table)
                if not original:
                    continue
                check(f"roundtrip table {arm}/{name}", name in exported)
                if name not in exported:
                    continue
                check(f"roundtrip authored column names/types {arm}/{name}", [(c["name"], c["datatype"]) for c in table["columns"]] == [(c["name"], c["datatype"]) for c in exported[name]["columns"]])
                returned = records(exported[name])
                check(f"roundtrip rows {arm}/{name}", len(original) == len(returned))
                for index, (a, b) in enumerate(zip(original, returned)):
                    for field, value in a.items():
                        if value is not None:
                            check(f"roundtrip cell {arm}/{name}/{index}/{field}", b.get(field) == value)
            converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
            check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
            check(f"classified warning only {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
            check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 300000)
            check(f"outcome complete {arm}", outcome["arms"][arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"])
            log = (RUN / f"{arm}.log").read_text(encoding="latin-1")
            failures = [float(time) for time in re.findall(rf"Time: ([\d.]+) <TEACH-AIR-01,0> {failure_text}", log)]
            window_failures = [time for time in failures if 9 <= time < 24]
            schedule = {time: re.findall(rf"Time: {time} <TEACH-AIR-01,0> Next random failure will occur ([^\r\n]+)", log) for time in (9, 24)}
            check(f"h9 reschedule marker {arm}", len(schedule[9]) >= 2)
            check(f"h24 reschedule marker {arm}", len(schedule[24]) >= 1)
            if kind == "item":
                check(f"item h24 terminal no-exposure sentinel {arm}", schedule[24][-1] == "1e+010")
            else:
                check(f"FM finite next-failure at h24 {arm}", any(float(text) < 1e9 for text in schedule[24]))
            successes = len(re.findall(r"mission success:", log))
            aborts = len(re.findall(r"mission aborted:", log))
            cancelled = len(re.findall(r"mission cancelled:", log))
            completed_repairs = len(re.findall(r"^Time: [\d.]+\s+system (?:CM|SURP) task \d+ on .* completed$", log, re.M))
            check(f"three mission outcomes {arm}", successes + aborts + cancelled == 3)
            report_tables = table_map(native_report(RUN / f"{arm}-report-raw.json"), "report")
            check(f"four default report tables {arm}", set(report_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
            system = records(report_tables["SystemResults"])
            stock = records(report_tables["StockTotalResults"])
            summary = records(report_tables["ResultSummary"])
            bins = 120 if kind == "item" else 72
            check(f"System/Stock half-hour bins {arm}", all(len(group) == bins and all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(group)) for group in (system, stock)))
            check(f"reported failures {arm}", sum(row["NFAIL"] or 0 for row in system) == len(failures))
            check(f"repair completions bounded {arm}", 0 <= completed_repairs <= len(failures) and len(failures) - completed_repairs <= 1)
            repair_bin_integral = sum(row["NSYRP"] or 0 for row in system)
            check(f"repair bins versus event completions {arm}", completed_repairs - 1e-6 <= repair_bin_integral < completed_repairs + 1.000001)
            check(f"mission summary success ratio {arm}", len(summary) == 1 and abs(summary[0]["MSUF"] - successes / 3) < 1e-6)
            check(f"no stock backorder {arm}", all((row["NBO"] or 0) == 0 and (row["NBOU"] or 0) == 0 for row in stock))
            check(f"terminal readiness bounded {arm}", 0 <= system[-1]["NSYRY"] <= 1)
            readiness = re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0> nbr ready (increased|decreased) at unit:", log)
            final_ready = 1 if not readiness or readiness[-1][1] == "increased" else 0
            check(f"terminal readiness agrees with event ledger {arm}", (system[-1]["NSYRY"] == 1) == bool(final_ready))
            observed[arm] = {"failures": failures, "completed_repairs": completed_repairs, "repair_bin_integral": repair_bin_integral, "window_failures": window_failures, "h9_next_failure": schedule[9], "h24_next_failure": schedule[24], "mission_success": successes, "mission_abort": aborts, "mission_cancelled": cancelled, "terminal_ready_interval_average": system[-1]["NSYRY"]}

for kind in ("item", "fm"):
    check(f"physical h9-24 panel contrast {kind}", any(observed[f"{kind}-seed{s}-control"]["window_failures"] != observed[f"{kind}-seed{s}-factor4"]["window_failures"] for s in (1, 2, 3)))
    for seed in (1, 2, 3):
        check(f"h9 next-failure schedule paired contrast {kind}/seed{seed}", observed[f"{kind}-seed{seed}-control"]["h9_next_failure"] != observed[f"{kind}-seed{seed}-factor4"]["h9_next_failure"])

check("finite item h24 reschedule in paired seeds", any(all(any(float(x) < 1e9 for x in observed[f"item-seed{s}-{arm}"]["h24_next_failure"]) for arm in ("control", "factor4")) for s in (1, 2, 3)))
check("item third mission exposes h24 in finite pair", any(all("Time: 23 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting" in (RUN / f"item-seed{s}-{arm}.log").read_text(encoding="latin-1") and "Time: 25 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission" in (RUN / f"item-seed{s}-{arm}.log").read_text(encoding="latin-1") and any(float(x) < 1e9 for x in observed[f"item-seed{s}-{arm}"]["h24_next_failure"]) for arm in ("control", "factor4")) for s in (1, 2, 3)))
failed = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-i06-scheduled-reliability-independent-replay/v1",
    "run_id": RUN.name,
    "verdict": "GO_BOUNDED" if not failed else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "observed": observed,
    "reason": "Both kinds show scheduled h9/h24 next-failure recomputation absent at h24 in their accepted parents. The item seed1 pair has finite h24 recomputation during its h23-25 mission. Fixed-seed physical h9-24 contrasts and report ledgers reconcile. Logs do not print the applied numerical factor.",
    "limits": "Three fixed seeds each, one traditional item and one explicit position mode. Timed rescheduling and bounded event outcomes are observed; numerical factor values are source/manual claims, not directly printed by native logs. No population hazard estimate or general factor law.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in verdict.items() if key != "observed"}, indent=2))
if failed:
    raise SystemExit(1)
