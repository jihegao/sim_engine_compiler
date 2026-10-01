"""Independent read-only replay of C09.var01's three fixed-seed native runs.

Standard library only; no author-code imports or native executable invocation.
Only the adjacent deterministic JSON report is written.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
PARENT = ROOT / "C09-var04-remote-maintenance-resource-v1.0.0" / "local-input.json"
CATALOG_PARENT = ROOT / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
ARMS = {"short": .25, "equal": .5, "long": .75}
RUNS = {name: CASE / "runs" / f"c09-var01-{name}-20261002-01" for name in ARMS}
FILES = {
    "parent": PARENT,
    "catalog_parent": CATALOG_PARENT,
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
EXPECTED_WORK = {
    "short": [(8.53243, 9.03243), (8.78243, 9.28243)],
    "equal": [(8.53243, 9.03243), (9.03243, 9.53243)],
    "long": [(8.53243, 9.03243), (9.03243, 9.53243)],
}
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    if native:  # Installed SIMLOX may leave a trailing comma after its last table.
        text = re.sub(r",(?=\s*[}\]])", "", text)
    return json.loads(text)


def check(name, passed, detail=None):
    checks.append({"name": name, "pass": bool(passed), **({"detail": detail} if detail is not None else {})})


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [(instance["instance_name"], row)
            for instance in table["instances"] for row in instance["rows"]]


def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for _, row in rows(table)]


def field_index(table, name):
    return [column["name"] for column in table["columns"]].index(name)


def near(x, y, tolerance=2e-5):
    return math.isclose(x, y, rel_tol=0, abs_tol=tolerance)


def reconstruct(parent, arm, travel):
    document = copy.deepcopy(parent)
    t = tables(document)
    t["ProblemDescription"]["instances"][0]["rows"][0][field_index(t["ProblemDescription"], "PDESC")] = f"C09.var01 remote travel {arm} versus 0.5-hour local primary repair wait"
    allocation = t["ResourceAllocation"]
    mechanic_rows = [r for _, r in rows(allocation) if r[field_index(allocation, "RID")] == "P-MECH"]
    check(f"{arm} unique parent local mechanic", len(mechanic_rows) == 1)
    new_mechanic = copy.deepcopy(mechanic_rows[0])
    new_mechanic[field_index(allocation, "STID")] = "BASE-02"
    allocation["instances"][0]["rows"].append(new_mechanic)
    fields = (("RID", "string", True), ("STID", "string", True), ("RSTID", "string", True),
              ("TFRS", "double", False), ("TTRS", "double", False),
              ("TTRSS", "double", False), ("NOTE", "string", False))
    route = {"columns": [{**{"datatype": datatype}, **({"key": True} if key else {}), "name": name}
                         for name, datatype, key in fields],
             "instances": [{"instance_name": "", "rows": [["P-MECH", "BASE-01", "BASE-02", travel, .5, .125, None]]}],
             "name": "ResourceRemoteSupport"}
    document["model"]["tables"].append(route)
    return document


def event_times(log, phrase):
    return [float(value) for value in re.findall(r"Time: ([0-9.]+)\s+" + phrase, log)]


def main():
    contract = read(CASE / "contract.json")
    parent = read(PARENT)
    check("direct behavior parent SHA", sha(PARENT) == contract["parent_input_sha256"])
    check("catalog C03 parent SHA", sha(CATALOG_PARENT) == contract["catalog_parent_input_sha256"])
    check("installed manual SHA", sha(FILES["manual"]) == contract["manual_sha256"])
    check("installed dictionary SHA", sha(FILES["dictionary"]) == contract["dictionary_sha256"])
    current_shas = {key: sha(path) for key, path in FILES.items()}
    model_tables = {}
    gui = None
    raw_count = 0
    outcomes = {}
    for arm, travel in ARMS.items():
        source = CASE / f"{arm}-input.json"
        run = RUNS[arm]
        reconstructed = reconstruct(parent, arm, travel)
        exact_bytes = (json.dumps(reconstructed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        check(f"{arm} exact parent-derived source bytes", source.read_bytes() == exact_bytes)
        check(f"{arm} source SHA and copied input", sha(source) == contract["input_sha256"][arm] == sha(run / "input.json"))
        model_tables[arm] = tables(read(source))
        source_names = set(model_tables[arm])
        parent_names = set(tables(parent))
        changed = {name for name in source_names if model_tables[arm][name] != tables(parent).get(name)}
        check(f"{arm} exact parent table delta", changed == {"ProblemDescription", "ResourceAllocation", "ResourceRemoteSupport"} and source_names == parent_names | {"ResourceRemoteSupport"}, sorted(changed))
        route = model_tables[arm]["ResourceRemoteSupport"]
        check(f"{arm} route times and identities", [row for _, row in rows(route)] == [["P-MECH", "BASE-01", "BASE-02", travel, .5, .125, None]])
        mechanics = [r for r in records(model_tables[arm]["ResourceAllocation"]) if r["RID"] == "P-MECH"]
        check(f"{arm} one mechanic at each station", len(mechanics) == 2 and {(r["STID"], r["RQTY"]) for r in mechanics} == {("BASE-01", 1), ("BASE-02", 1)})

        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        check(f"{arm} invocation SHA/identity", sha(run / "invocation.json") == closure["invocation_sha256"] and invocation["run_id"] == closure["run_id"] == run.name and invocation["variant"] == arm)
        check(f"{arm} session-0 SSH ancestry", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        check(f"{arm} host queue mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        identity = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
        if gui is None: gui = identity
        check(f"{arm} GUI PID/start continuity", identity == gui and identity[:2] == (13340, 1) and all(s["gui_preserved"] for s in steps))
        check(f"{arm} five successful native/check steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" for s in steps))
        check(f"{arm} unchanged run-bound sources", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None)
        for key, recorded in closure["source_hashes_before"].items():
            actual = sha(source) if key == "input" else sha(Path(invocation["planned_check"]["executable"])) if key == "python" else current_shas[key]
            check(f"{arm} source seal {key}", recorded == actual)
        raw_count += len(closure["raw"])
        check(f"{arm} 12 raw file seals", len(closure["raw"]) == 12)
        for name, seal in closure["raw"].items():
            file = run / name
            check(f"{arm} raw {name}", file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"])
        check(f"{arm} sealed raw file set complete", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})

        exported = tables(read(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in model_tables[arm].items() if rows(table)]
        check(f"{arm} 23 row-containing source tables", len(populated) == 23)
        for name in populated:
            before, after = model_tables[arm][name], exported.get(name)
            check(f"{arm} exact {name} roundtrip", after is not None and [c["name"] for c in before["columns"]] == [c["name"] for c in after["columns"]] and rows(before) == rows(after))
        conversion_log = (run / "run.log").read_text(encoding="utf-8-sig")
        summary = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion_log)
        check(f"{arm} converter summary exists", summary is not None)
        diagnostics = tuple(map(int, summary.groups())) if summary else None
        check(f"{arm} zero errors, classified warnings", diagnostics == (0, 2, 0) and "(warning #108)" in conversion_log and "(warning #126)" in conversion_log)
        check(f"{arm} nonempty SXO and report", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        work_starts = event_times(log, r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,[01]> starts performing")
        work_ends = event_times(log, r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,[01]> completed")
        check(f"{arm} two simultaneous DIRP task starts", len(re.findall(r"Time: 8\.53243\s+system DIRP task \d+ on <TEACH-AIR-01,[01]> started", log)) == 2)
        check(f"{arm} repair performance intervals", list(zip(work_starts, work_ends)) == EXPECTED_WORK[arm], list(zip(work_starts, work_ends)))
        if arm == "short":
            forward = [(8.53243, "remote resource transport task 3 starts with 1 resources, transportation time: 0.25"), (8.78243, "remote resource transport task 3 arrives with 1 resources")]
            back = [(9.03243, "return resource transport task 0 starts with 1 resources, transportation time: 0.5"), (9.53243, "return resource transport task 0 arrives with 1 resources")]
            check("short borrow and return events", all(f"Time: {time:g}  {message}" in log for time, message in forward + back))
            check("short one forward and one return task", log.count("remote resource transport task 3 starts with 1 resources") == 1 and log.count("return resource transport task 0 starts with 1 resources") == 1)
            check("short no support cancellation", "Remote resource support cancelled" not in log)
        else:
            check(f"{arm} remote support cancelled at tie/long boundary", "Time: 8.53243  <P-MECH at <BASE-01,0>> Remote resource support cancelled" in log)
            check(f"{arm} no forward or return transport", "remote resource transport task" not in log and "return resource transport task" not in log)

        report = tables(read(run / "report-raw.json", native=True), "report")
        system, stock, resources = (records(report[name]) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        check(f"{arm} 72 aligned half-hour report bins", all(len(t) == 72 for t in (system, stock, resources)) and all(s["STINT"] == t["STINT"] == r["STINT"] == index * .5 and s["ETINT"] == t["ETINT"] == r["ETINT"] == (index + 1) * .5 for index, (s, t, r) in enumerate(zip(system, stock, resources))))
        check(f"{arm} two failures and repairs", sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == 2)
        check(f"{arm} terminal two ready", near(system[-1]["NSYRY"], 2))
        check(f"{arm} no stock demand", all((r["NBO"] or 0) == (r["NDD"] or 0) == 0 for r in stock))
        conservation_error = max(abs(r["NR"] + r["NRRT"] - r["NRN"]) for r in resources)
        check(f"{arm} four-resource conservation", conservation_error < 2e-6 and all(near(r["NRN"], 4) for r in resources), conservation_error)
        transit_hours = sum(r["NRRT"] * .5 for r in resources)
        waiting_hours = sum(r["NRW"] * .5 for r in resources)
        check(f"{arm} transit hours", near(transit_hours, .75 if arm == "short" else 0), transit_hours)
        check(f"{arm} wait hours", near(waiting_hours, .25 if arm == "short" else .5), waiting_hours)
        check(f"{arm} terminal transport cleared", near(resources[-1]["NRRT"], 0) and near(resources[-1]["NR"], 4))
        outcomes[arm] = {"run_id": run.name, "source_sha256": sha(source), "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log"), "converter_errors_warnings_notes": diagnostics, "repair_work_start_end": list(zip(work_starts, work_ends)), "resource_transit_hours": transit_hours, "resource_wait_hours": waiting_hours, "resource_conservation_max_abs_error": conservation_error, "terminal_ready": system[-1]["NSYRY"]}

    check("36 raw SHA-256 seals", raw_count == 36)
    check("three-arm source differs only in description and forward travel", {name for name in model_tables["equal"] if model_tables["equal"][name] != model_tables["short"].get(name)} == {"ProblemDescription", "ResourceRemoteSupport"} and {name for name in model_tables["long"] if model_tables["long"][name] != model_tables["short"].get(name)} == {"ProblemDescription", "ResourceRemoteSupport"})
    failed = [item for item in checks if not item["pass"]]
    report = {"schema": "independent-c09-var01-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded fixed-seed travel-vs-local-wait CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "raw_seals": raw_count, "outcomes": outcomes, "limitations": ["Observed .25-hour borrowing and .5/.75-hour cancellation support a strict boundary in this fixed setup only, not every local-wait rule or population frequency.", "Aggregate ResourceResults cannot identify which interchangeable P-MECH instance returns: the return task begins at 9.03243 while the second repair continues until 9.28243.", "No general multiple-resource, shift, cost, GUI, or cross-engine conclusion."]}
    OUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failures": failed, "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__": main()
