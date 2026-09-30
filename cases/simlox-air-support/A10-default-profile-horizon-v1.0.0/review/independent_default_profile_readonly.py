"""Read-only, standard-library replay of the sealed A10 default-profile pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = Path(__file__).with_name("independent-default-profile-2026-09-30.json")
RUNS = {v: CASE / "runs" / f"a10-default-{v}-20260930-01" for v in ("48h", "50h")}
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GUI = {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:  # SIMLOX report output has a trailing comma after the last table.
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def ck(label, okay, detail=None):
    result = {"name": label, "passed": bool(okay)}
    if not okay and detail is not None:
        result["detail"] = detail
    checks.append(result)


def tabmap(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table.get("instances", []) for row in instance.get("rows", [])]


def fields(table, row):
    return dict(zip((column["name"] for column in table["columns"]), row))


def series(table, column):
    pos = [c["name"] for c in table["columns"]].index(column)
    return [r[pos] for r in rows(table)]


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def changed_fields(before, after):
    if before["columns"] != after["columns"] or len(rows(before)) != len(rows(after)):
        return {"<schema-or-row-count>"}
    names = [c["name"] for c in before["columns"]]
    return {names[j] for left, right in zip(rows(before), rows(after)) for j in range(len(names)) if left[j] != right[j]}


def main():
    parent = obj(PARENT)
    contract = obj(CASE / "contract.json")
    source = {v: obj(CASE / f"{v}-input.json") for v in RUNS}
    pt = tabmap(parent)
    st = {v: tabmap(source[v]) for v in RUNS}
    ck("published A01 parent SHA and signoff", sha(PARENT) == PARENT_SHA and any(PARENT.parent.glob("cli-scope-signoff-*.md")))
    ck("installed manual SHA and physical pages", sha(MANUAL) == MANUAL_SHA and contract["source"]["manual_sha256"] == MANUAL_SHA and contract["source"]["pages"] == [194, 195, 196, 276, 277, 278, 279, 280])
    ck("contract names 48h and 50h variants", contract["case_id"] == "A10" and set(contract["configuration"]["variants"]) == set(RUNS))
    removed = {"MissionType", "OperationProfile", "Operations"}
    new = {"SystemDeploymentUtilization"}
    changed = {"ProblemDescription", "Control", "SystemDeployment", "ResultCollection"}
    for variant, tab in st.items():
        prefix = variant + ": "
        horizon = 48 if variant == "48h" else 50
        ck(prefix + "exact removed and added table set", set(pt) - set(tab) == removed and set(tab) - set(pt) == new and len(tab) == len(pt) - 2)
        ck(prefix + "exact changed inherited table set", {name for name in pt if name in tab and tab[name] != pt[name]} == changed)
        ck(prefix + "exact changed fields in inherited tables", changed_fields(pt["ProblemDescription"], tab["ProblemDescription"]) == {"PDESC"} and changed_fields(pt["Control"], tab["Control"]) == {"SIMPE", "RCEND"} and changed_fields(pt["SystemDeployment"], tab["SystemDeployment"]) == {"UTIL"} and changed_fields(pt["ResultCollection"], tab["ResultCollection"]) == {"RCEND"})
        ck(prefix + "other parent tables unchanged", all(tab[n] == pt[n] for n in pt if n not in removed | changed))
        ck(prefix + "11 row-containing source tables", sum(bool(rows(t)) for t in tab.values()) == 11)
        control = fields(tab["Control"], rows(tab["Control"])[0])
        ck(prefix + "simulation and collection horizon", control["SIMPE"] == control["RCEND"] == horizon and all(fields(tab["ResultCollection"], r)["RCEND"] == horizon for r in rows(tab["ResultCollection"])))
        deploy = fields(tab["SystemDeployment"], rows(tab["SystemDeployment"])[0])
        util = fields(tab["SystemDeploymentUtilization"], rows(tab["SystemDeploymentUtilization"])[0])
        ck(prefix + "one-aircraft OPHOURS and MISSIONS utilization", len(rows(tab["SystemDeployment"])) == len(rows(tab["SystemDeploymentUtilization"])) == 1 and deploy["SID"] == util["SID"] == "TEACH-AIR-01" and deploy["USTID"] == util["USTID"] == "TEACH-UNIT" and deploy["QTYPS"] == 1 and close(deploy["UTIL"], .25) and util["OPID"] == "MISSIONS" and close(util["UTIL"], 1/12))
        ck(prefix + "new utilization row has exact five-field schema", [(c["name"], c["datatype"], c.get("key", False)) for c in tab["SystemDeploymentUtilization"]["columns"]] == [("SID", "string", True), ("USTID", "string", True), ("OPID", "string", True), ("UTIL", "double", False), ("NOTE", "string", False)] and util["NOTE"] is None)
    ck("variant source changes only horizon and description", {n for n in st["48h"] if st["48h"][n] != st["50h"][n]} == {"ProblemDescription", "Control", "ResultCollection"})
    runner = (CASE / "run_native_ssh.ps1").read_text(errors="replace")
    ck("runner contains session0 SSH, mutex, GUI and source guard", all(x in runner for x in ("$env:SSH_CONNECTION", ".SessionId -ne 0", "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui", "source fingerprint changed during native run")))

    observed = {}
    for variant, run in RUNS.items():
        prefix = variant + ": "
        horizon = 48 if variant == "48h" else 50
        duration = 3 if variant == "48h" else 3.125
        first_start = (12 - duration) / 2
        expected_starts = [first_start + 12*i for i in range(4)]
        expected_ends = [time + duration for time in expected_starts]
        inv, closure, steps = (obj(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        expected_hashes = {"input": sha(CASE / f"{variant}-input.json"), "parent": sha(PARENT), "contract": sha(CASE / "contract.json"), "builder": sha(CASE / "build.py"), "checker": sha(CASE / "check_roundtrip.py"), "runner_script": sha(CASE / "run_native_ssh.ps1")}
        ck(prefix + "frozen source copied into run", sha(run / "input.json") == expected_hashes["input"] == inv["input_sha256"])
        ck(prefix + "invocation and closure identity", inv["run_id"] == closure["run_id"] == run.name and inv["variant"] == variant and closure["invocation_sha256"] == sha(run / "invocation.json"))
        ck(prefix + "all current source hashes match before and after", all(inv["source_hashes_before"].get(k) == value and closure["source_hashes_before"].get(k) == value and closure["source_hashes_after"].get(k) == value for k, value in expected_hashes.items()))
        ck(prefix + "session0 SSH mutex and GUI identity", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == GUI)
        raw = closure["raw"]
        ck(prefix + "all 12 raw sizes and SHA seals", len(raw) == 12 and all((run / n).is_file() and len((run / n).read_bytes()) == meta["bytes"] and sha(run / n) == meta["sha256"] for n, meta in raw.items()))
        ck(prefix + "five successful steps preserve GUI", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True for s in steps))
        ck(prefix + "four CLI planned arguments match actual steps", [cmd["name"] for cmd in inv["planned_commands"]] == ["import", "export", "calc", "jsonreport"] and all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)))
        exported = tabmap(obj(run / "roundtrip-raw.json"))
        ck(prefix + "each source schema/business row roundtrips", all(table["columns"] == exported[name]["columns"] and (not rows(table) or rows(table) == rows(exported[name])) for name, table in st[variant].items()))
        ck(prefix + "roundtrip checker corroboration", obj(run / "roundtrip-validation.json")["passed"] is True)
        runlog = (run / "run.log").read_text(errors="replace")
        ck(prefix + "zero conversion errors, classified diagnostics", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 4" in runlog and sorted(map(int, re.findall(r"warning #(\d+)", runlog))) == [108, 126] and sorted(map(int, re.findall(r"notice #(\d+)", runlog))) == [115, 116, 117, 488] and not re.search(r"error #\d+", runlog))
        log = (run / "model.log").read_text(errors="replace")
        generated = "TEACH-UNIT_TEACH-AIR-01_MISSION"
        pattern = rf"^Time: ([0-9.]+) <<{generated}>,TEACH-UNIT,0,0,([0-9]+)> "
        created = re.findall(pattern + "mission created:", log, re.M)
        starts = re.findall(pattern + r"mission starting, duration: ([0-9.]+) : <(TEACH-AIR-01,0)>", log, re.M)
        successes = re.findall(pattern + "mission success:", log, re.M)
        completions = re.findall(pattern + r"mission completed: <(TEACH-AIR-01,0)>", log, re.M)
        orders = re.findall(rf"^Time: ([0-9.]+) <TEACH-UNIT> mission ordered: <{generated}>", log, re.M)
        ck(prefix + "four distinct generated mission IDs only", len(created) == len(starts) == len(successes) == len(completions) == len(orders) == 4 and [int(i) for _, i in created] == [0, 1, 2, 3] and len(re.findall(r"mission starting,", log)) == 4 and "BASIC-MISSION" not in log)
        ck(prefix + "four centered starts and mission durations", all(close(float(starts[i][0]), expected_starts[i]) and int(starts[i][1]) == i and close(float(starts[i][2]), duration) for i in range(4)))
        ck(prefix + "same generated mission identity through creation, success, completion", all(int(created[i][1]) == int(starts[i][1]) == int(successes[i][1]) == int(completions[i][1]) == i and close(float(created[i][0]), expected_starts[i]) and close(float(orders[i]), expected_starts[i]) and close(float(successes[i][0]), expected_ends[i]) and close(float(completions[i][0]), expected_ends[i]) for i in range(4)))
        ck(prefix + "one aircraft returns and becomes ready four times", len(re.findall(r"System arrives <TEACH-AIR-01,0>, mission success", log)) == 4 and len(re.findall(r"System ready <TEACH-AIR-01,0>", log)) == 8)
        report = obj(run / "report-raw.json", native=True)
        rep = tabmap(report, "report")
        summary = fields(rep["ResultSummary"], rows(rep["ResultSummary"])[0])
        sys, stock = rep["SystemResults"], rep["StockTotalResults"]
        sr = rows(sys)
        nbin = horizon * 2
        ck(prefix + "half-hour contiguous system and stock ledgers", len(sr) == len(rows(stock)) == nbin and all(close(r[2], .5*i) and close(r[3], .5*(i+1)) for i, r in enumerate(sr)) and all(close(r[0], .5*i) and close(r[1], .5*(i+1)) for i, r in enumerate(rows(stock))))
        expected_occupancy = [sum(max(0., min((i+1)*.5, end) - max(i*.5, start)) / .5 for start, end in zip(expected_starts, expected_ends)) for i in range(nbin)]
        ck(prefix + "event-derived fractional operation occupancy every bin", all(close(actual, expected) for actual, expected in zip(series(sys, "NSYMO"), expected_occupancy)) and all(close(actual, expected) for actual, expected in zip(series(sys, "STACC"), expected_occupancy)))
        ck(prefix + "availability/ready ledger every bin", all(close(active, expected) for active, expected in zip(series(sys, "NSYMA"), expected_occupancy)) and all(close(ready, 1-expected) for ready, expected in zip(series(sys, "NSYRY"), expected_occupancy)) and all(close(a, 1) for a in series(sys, "NSYA")))
        target_hours = 12 if variant == "48h" else 12.5
        ck(prefix + "operation-hour integral and no failure/maintenance", close(sum(.5*x for x in series(sys, "NSYMO")), target_hours) and max(series(sys, "NFAIL")) == max(series(sys, "NREPT")) == max(series(sys, "NPMT")) == 0)
        ck(prefix + "stock ledger has no backorder or demand", max(series(stock, "NBO")) == 0 and max(series(stock, "NDF")) == 0 and max(series(stock, "NDD")) == 0)
        ck(prefix + "summary metric scope and terminal ready", summary["NREP"] == 1 and summary["RTIUP"] == horizon and summary["MTMF"] == summary["STMF"] == 1 and summary["MSTF"] == summary["MSUF"] == 0 and close(series(sys, "NSYRY")[-1], 1) and close(series(sys, "NSYMO")[-1], 0))
        observed[variant] = {"generated_mission_type": f"<{generated}>", "mission_ids": [int(i) for _, i in created], "starts": [float(x[0]) for x in starts], "durations": [float(x[2]) for x in starts], "completions": [float(x[0]) for x in completions], "operating_aircraft_hours": sum(.5*x for x in series(sys, "NSYMO")), "report_bins": nbin, "terminal_ready": series(sys, "NSYRY")[-1], "summary": {k: summary[k] for k in ("NREP", "RTIUP", "MTMF", "MSTF", "MSUF", "STMF")}, "report_sha256": sha(run / "report-raw.json")}

    ck("50h has two-hour remainder and no fifth mission", len(observed["50h"]["mission_ids"]) == 4 and observed["50h"]["starts"][-1] < 48 and observed["50h"]["completions"][-1] < 48 and observed["50h"]["report_bins"] == 100)
    outcome = {"schema": "simlox-a10-independent-default-profile-readonly/v1", "reviewer": "Standalone standard-library raw replay; no author imports or native invocation", "passed": all(c["passed"] for c in checks), "passed_count": sum(c["passed"] for c in checks), "failed_count": sum(not c["passed"] for c in checks), "failed": [c for c in checks if not c["passed"]], "checks": checks, "hashes": {"parent_input": sha(PARENT), "manual_pdf": sha(MANUAL), "contract": sha(CASE / "contract.json"), **{v + "_input": sha(CASE / f"{v}-input.json") for v in RUNS}, **{v + "_report": observed[v]["report_sha256"] for v in RUNS}}, "observed": observed, "manual_read": "Installed manual pp194-195 gives implicit default-profile identities, centered cycles and 50h remainder scaling; p194 comparison text conflicts with worked examples, so this review uses native events.", "decision": "bounded_pair_accepted" if all(c["passed"] for c in checks) else "review_failed", "limits": ["One deployed aircraft in one explicit unit; no multi-type interaction or explicit-profile suppression control.", "Generated default mission log has success/completion events, while ResultSummary MSTF/MSUF remain zero; the report supports MTMF/STMF=1 only for those summary fields.", "GUI Profile View rendering and cross-engine parity were not tested."]}
    OUT.write_bytes((json.dumps(outcome, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": outcome["passed"], "passed_count": outcome["passed_count"], "failed": outcome["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
