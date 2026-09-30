"""Independent stdlib replay of sealed A11 explicit-formation trio."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = Path(__file__).with_name("independent-formation-2026-09-30.json")
VARIANTS = ("ab-high", "aa-high", "b-missing")
RUNS = {v: CASE / "runs" / f"a11-form-{v}-20260930-01" for v in VARIANTS}
PARENT_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GUI = {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}
checks = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    if native:  # Native report export has a trailing comma after its last table.
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def check(label, condition, detail=None):
    item = {"name": label, "passed": bool(condition)}
    if not condition and detail is not None:
        item["detail"] = detail
    checks.append(item)


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table.get("instances", []) for row in instance.get("rows", [])]


def record(table, row):
    return dict(zip((column["name"] for column in table["columns"]), row))


def keyed(table, key):
    return {record(table, row)[key]: record(table, row) for row in rows(table)}


def field_series(table, field):
    pos = [c["name"] for c in table["columns"]].index(field)
    return [row[pos] for row in rows(table)]


def main():
    parent = load(PARENT)
    contract = load(CASE / "contract.json")
    source = {v: load(CASE / f"{v}-input.json") for v in VARIANTS}
    parent_tables = tables(parent)
    source_tables = {v: tables(source[v]) for v in VARIANTS}
    check("published A11 parent hash and signoff", digest(PARENT) == PARENT_SHA and (PARENT.parent / "cli-scope-signoff-2026-09-30.md").is_file())
    check("installed manual hash and cited pages", digest(MANUAL) == MANUAL_SHA and contract["source"]["manual_sha256"] == MANUAL_SHA and contract["source"]["pages"] == [184, 185, 281, 282, 292, 293, 294])
    check("contract declares three formations variants", contract["case_id"] == "A11" and set(contract["configuration"]["variants"]) == set(VARIANTS))
    new_tables = {"Formation", "FormationSystem", "MissionFormation"}
    check("all variants add exact three formation tables", all(set(source_tables[v]) == set(parent_tables) | new_tables for v in VARIANTS))
    for v in VARIANTS:
        st = source_tables[v]
        changed = {name for name in parent_tables if st[name] != parent_tables[name]}
        expected_changed = {"ProblemDescription"} if v != "b-missing" else {"ProblemDescription", "SystemDeployment", "Unit"}
        check(v + ": exact inherited changed-table set", changed == expected_changed)
        check(v + ": untouched parent table equality", all(st[n] == parent_tables[n] for n in parent_tables if n not in expected_changed))
        check(v + ": 17 source row-containing tables", sum(bool(rows(t)) for t in st.values()) == 17)
        check(v + ": unchanged per-type MissionSystem A+B minima", st["MissionSystem"] == parent_tables["MissionSystem"])
        formations = keyed(st["Formation"], "FID")
        frows = [record(st["FormationSystem"], r) for r in rows(st["FormationSystem"])]
        check(v + ": two exact complete formation definitions", set(formations) == {"FORM-AB", "FORM-AA"} and {(r["FID"], r["SID"], r["NOS"]) for r in frows} == {("FORM-AB", "TEACH-AIR-01", 1), ("FORM-AB", "TEACH-AIR-02", 1), ("FORM-AA", "TEACH-AIR-01", 2)} and len(frows) == 3)
        priority = keyed(st["MissionFormation"], "FID")
        expected_pri = {"FORM-AB": 2, "FORM-AA": 1} if v == "aa-high" else {"FORM-AB": 1, "FORM-AA": 2}
        check(v + ": precise mission formation priority", set(priority) == set(expected_pri) and all(priority[f]["PRI"] == p and priority[f]["MTID"] == "BASIC-MISSION" and priority[f]["ALOAA"] is None for f, p in expected_pri.items()))
        deployments = keyed(st["SystemDeployment"], "SID")
        check(v + ": B deployed exactly when specified", set(deployments) == ({"TEACH-AIR-01"} if v == "b-missing" else {"TEACH-AIR-01", "TEACH-AIR-02"}) and deployments["TEACH-AIR-01"]["QTYPS"] == 2 and (v == "b-missing" or deployments["TEACH-AIR-02"]["QTYPS"] == 1))
    check("AA-high changes only priority and label from AB-high", {n for n in source_tables["ab-high"] if source_tables["ab-high"][n] != source_tables["aa-high"][n]} == {"ProblemDescription", "MissionFormation"})
    check("B-missing changes deployment, unit and label from AB-high", {n for n in source_tables["ab-high"] if source_tables["ab-high"][n] != source_tables["b-missing"][n]} == {"ProblemDescription", "SystemDeployment", "Unit"})
    runner = (CASE / "run_native_ssh.ps1").read_text(errors="replace")
    check("runner contains session0 SSH queue GUI and source seal guards", all(x in runner for x in ("$env:SSH_CONNECTION", ".SessionId -ne 0", "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui", "source fingerprint changed during native run")))

    observed = {}
    for v, run in RUNS.items():
        prefix = v + ": "
        inv = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        expected_hashes = {
            "input": digest(CASE / f"{v}-input.json"), "parent": digest(PARENT), "contract": digest(CASE / "contract.json"),
            "builder": digest(CASE / "build.py"), "checker": digest(CASE / "check_roundtrip.py"), "runner_script": digest(CASE / "run_native_ssh.ps1"),
        }
        check(prefix + "frozen input copy and invocation identity", digest(run / "input.json") == expected_hashes["input"] == inv["input_sha256"] and inv["variant"] == v and inv["run_id"] == closure["run_id"] == run.name)
        check(prefix + "invocation SHA bound in closure", closure["invocation_sha256"] == digest(run / "invocation.json"))
        check(prefix + "all source hashes before and after", all(inv["source_hashes_before"].get(k) == value and closure["source_hashes_before"].get(k) == value and closure["source_hashes_after"].get(k) == value for k, value in expected_hashes.items()))
        check(prefix + "session0 SSH, mutex, GUI identity", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == GUI)
        raw = closure["raw"]
        check(prefix + "12 raw artifact sizes and hashes", len(raw) == 12 and all((run / n).is_file() and len((run / n).read_bytes()) == entry["bytes"] and digest(run / n) == entry["sha256"] for n, entry in raw.items()))
        check(prefix + "four native steps and checker exited zero with GUI preserved", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True for s in steps))
        check(prefix + "actual CLI arguments equal planned arguments", [s["name"] for s in inv["planned_commands"]] == ["import", "export", "calc", "jsonreport"] and all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)))
        exported = tables(load(run / "roundtrip-raw.json"))
        check(prefix + "all source schemas and business rows roundtrip", all(t["columns"] == exported[name]["columns"] and (not rows(t) or rows(t) == rows(exported[name])) for name, t in source_tables[v].items()))
        check(prefix + "roundtrip checker corroboration", load(run / "roundtrip-validation.json")["passed"] is True)
        runlog = (run / "run.log").read_text(errors="replace")
        check(prefix + "zero conversion errors and warning codes 108/126/126", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and sorted(map(int, re.findall(r"warning #(\d+)", runlog))) == [108, 126, 126] and not re.search(r"error #\d+", runlog))
        log = (run / "model.log").read_text(errors="replace")
        mission = "BASIC-MISSION,TEACH-UNIT,0,0,0"
        active = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission starting, duration: 2 :\s+Active Formation (FORM-A[AB]): (.+)$", log, re.M)
        complete = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission completed:\s+Active Formation (FORM-A[AB]): (.+)$", log, re.M)
        success = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission success:", log, re.M)
        expected_form = "FORM-AB" if v == "ab-high" else "FORM-AA"
        expected_instances = {"TEACH-AIR-01,0", "TEACH-AIR-02,2"} if v == "ab-high" else {"TEACH-AIR-01,0", "TEACH-AIR-01,1"}
        get_aircraft = lambda text: set(re.findall(r"<(TEACH-AIR-0[12],[0-9]+)>", text))
        check(prefix + "one mission active formation 8-10", len(active) == len(complete) == len(success) == 1 and float(active[0][0]) == 8 and float(complete[0][0]) == float(success[0]) == 10 and active[0][1] == complete[0][1] == expected_form and len(re.findall(r"mission starting,", log)) == 1)
        check(prefix + "active formation aircraft identities", get_aircraft(active[0][2]) == get_aircraft(complete[0][2]) == expected_instances and all(f"Time: 10 <{item.split(',')[0]},BASE-01,0> System arrives <{item}>" in log for item in expected_instances))
        check(prefix + "no other active formation marker", set(re.findall(r"Active Formation (FORM-[A-Z]+)", log)) == {expected_form})
        report = load(run / "report-raw.json", native=True)
        rep = tables(report, "report")
        summary = record(rep["ResultSummary"], rows(rep["ResultSummary"])[0])
        sys = rep["SystemResults"]
        stock = rep["StockTotalResults"]
        sr = rows(sys)
        check(prefix + "72 contiguous half-hour system and stock bins", len(sr) == len(rows(stock)) == 72 and all(abs(r[2] - i*.5) < 1e-8 and abs(r[3] - (i+1)*.5) < 1e-8 for i, r in enumerate(sr)) and all(abs(r[0] - i*.5) < 1e-8 and abs(r[1] - (i+1)*.5) < 1e-8 for i, r in enumerate(rows(stock))))
        check(prefix + "summary success, no failure or stock demand", summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(summary[k] == 1 for k in ("MTMF", "MSTF", "MSUF", "STMF")) and max(field_series(sys, "NFAIL")) == 0 and max(field_series(stock, "NBO")) == 0)
        operating = [2 if 8 <= i*.5 < 10 else 0 for i in range(72)]
        check(prefix + "all event-derived operating occupancy bins", field_series(sys, "NSYMO") == operating and field_series(sys, "STACC") == operating)
        ready_at_end = 2 if v == "b-missing" else 3
        check(prefix + "four aircraft-hours and terminal ready count", sum(x*.5 for x in field_series(sys, "NSYMO")) == 4 and field_series(sys, "NSYRY")[-1] == ready_at_end and field_series(sys, "NSYMO")[-1] == 0)
        observed[v] = {"active_formation": active[0][1], "aircraft": sorted(get_aircraft(active[0][2])), "start": float(active[0][0]), "success_completion": float(success[0]), "operating_aircraft_hours": sum(x*.5 for x in field_series(sys, "NSYMO")), "terminal_ready": field_series(sys, "NSYRY")[-1], "report_sha256": digest(run / "report-raw.json")}

    check("priority swap selects AA despite inherited B minimum", observed["aa-high"]["active_formation"] == "FORM-AA" and observed["aa-high"]["aircraft"] == ["TEACH-AIR-01,0", "TEACH-AIR-01,1"])
    check("absent B selects complete lower-priority AA", observed["b-missing"]["active_formation"] == "FORM-AA" and observed["b-missing"]["aircraft"] == ["TEACH-AIR-01,0", "TEACH-AIR-01,1"])
    report = {
        "schema": "simlox-a11-formation-independent-readonly/v1", "reviewer": "Standalone standard-library raw replay; no author imports or native invocation",
        "passed": all(x["passed"] for x in checks), "passed_count": sum(x["passed"] for x in checks), "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"parent_input": digest(PARENT), "manual_pdf": digest(MANUAL), "contract": digest(CASE / "contract.json"), **{v + "_input": digest(CASE / f"{v}-input.json") for v in VARIANTS}, **{v + "_report": observed[v]["report_sha256"] for v in VARIANTS}},
        "observed": observed,
        "manual_read": "Installed manual pp184-185 and 281-282,292-294 gives explicit formations priority over quantity requirements, searches formations in PRI order and selects a complete available formation.",
        "decision": "bounded_three_run_accepted" if all(x["passed"] for x in checks) else "review_failed",
        "limits": ["One fixed mission with two complete formations, ready aircraft, no failure and zero-duration preparation only.", "The B-missing log records FORM-AA selected; it does not expose an internal search trace explicitly showing FORM-AB tested and rejected. The fallback interpretation follows the frozen priority/deployment inputs plus this selection and the manual rule.", "No inference about ALOAA, equal priorities, later readiness, reconfiguration, multiple missions, GUI visual behavior or cross-engine parity."],
    }
    OUT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": report["passed"], "passed_count": report["passed_count"], "failed": report["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
