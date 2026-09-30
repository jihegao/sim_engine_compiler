"""Standalone standard-library replay of the frozen A11 paired native runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUTPUT = Path(__file__).with_name("independent-mixed-type-2026-09-30.json")
RUNS = {x: CASE / "runs" / f"a11-{x}-20260930-02" for x in ("control", "required")}
PARENT_HASH = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
MANUAL_HASH = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GUI = {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}
checks: list[dict] = []


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:  # SIMLOX JSON report exporter emits a trailing comma after its last table.
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def verify(name: str, ok, detail=None):
    check = {"name": name, "passed": bool(ok)}
    if not ok and detail is not None:
        check["detail"] = detail
    checks.append(check)


def tabmap(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(tab):
    return [row for inst in tab.get("instances", []) for row in inst.get("rows", [])]


def named(tab, row):
    return dict(zip((c["name"] for c in tab["columns"]), row))


def as_key(tab, key):
    return {named(tab, r)[key]: named(tab, r) for r in rows(tab)}


def report_series(tab, field):
    index = [c["name"] for c in tab["columns"]].index(field)
    return [r[index] for r in rows(tab)]


def main():
    contract = read_json(CASE / "contract.json")
    parent = read_json(PARENT)
    sources = {v: read_json(CASE / f"{v}-input.json") for v in RUNS}
    pt, ct, rt = (tabmap(x) for x in (parent, sources["control"], sources["required"]))
    verify("accepted A03 parent SHA-256", hash_file(PARENT) == PARENT_HASH)
    verify("accepted A03 signed package present", (PARENT.parent / "cli-scope-signoff-2026-09-29.md").is_file())
    verify("installed manual SHA-256 and cited physical pages", hash_file(MANUAL) == MANUAL_HASH and contract["source"]["manual_sha256"] == MANUAL_HASH and contract["source"]["pages"] == [184, 188, 302, 303, 304])
    verify("contract states one fixed mixed-type mission", contract["case_id"] == "A11" and contract["configuration"]["mission"]["scheduled_hour"] == 8 and contract["configuration"]["mission"]["duration_hours"] == 2)
    verify("contract describes preparation as zero duration", any("zero-duration preparation events" in item for item in contract["limits"]))
    verify("control preserves parent table set", set(ct) == set(pt))
    verify("parent-to-control edits restricted to four tables", {n for n in pt if pt[n] != ct[n]} == {"ProblemDescription", "System", "SystemDeployment", "Unit"})
    verify("all other A03 tables unchanged", all(pt[n] == ct[n] for n in pt if n not in {"ProblemDescription", "System", "SystemDeployment", "Unit"}))
    a_sys, b_sys = rows(ct["System"])
    a_dep, b_dep = rows(ct["SystemDeployment"])
    bs, bd = named(ct["System"], b_sys), named(ct["SystemDeployment"], b_dep)
    first_sys, first_dep = named(ct["System"], a_sys), named(ct["SystemDeployment"], a_dep)
    verify("parent first aircraft and deployment preserved", a_sys == rows(pt["System"])[0] and a_dep == rows(pt["SystemDeployment"])[0])
    verify("new system clones A except type and label", len(rows(ct["System"])) == 2 and bs["SID"] == "TEACH-AIR-02" and all(bs[k] == first_sys[k] for k in first_sys if k not in {"SID", "DESCR"}))
    verify("new deployment clones A except type and quantity", len(rows(ct["SystemDeployment"])) == 2 and bd["SID"] == "TEACH-AIR-02" and bd["QTYPS"] == 1 and all(bd[k] == first_dep[k] for k in first_dep if k not in {"SID", "QTYPS"}))
    verify("unit changes description only", len(rows(ct["Unit"])) == 1 and all(named(ct["Unit"], rows(ct["Unit"])[0])[k] == named(pt["Unit"], rows(pt["Unit"])[0])[k] for k in named(pt["Unit"], rows(pt["Unit"])[0]) if k != "DESCR"))
    verify("required differs only by MissionSystem and label", set(rt) == set(ct) | {"MissionSystem"} and {n for n in ct if ct[n] != rt[n]} == {"ProblemDescription"})
    systems, deployment = as_key(rt["System"], "SID"), as_key(rt["SystemDeployment"], "SID")
    verify("two A and one B in one mixed unit", set(systems) == set(deployment) == {"TEACH-AIR-01", "TEACH-AIR-02"} and deployment["TEACH-AIR-01"]["QTYPS"] == 2 and deployment["TEACH-AIR-02"]["QTYPS"] == 1 and deployment["TEACH-AIR-01"]["USTID"] == deployment["TEACH-AIR-02"]["USTID"] == "TEACH-UNIT")
    mt = named(rt["MissionType"], rows(rt["MissionType"])[0])
    op = named(rt["OperationProfile"], rows(rt["OperationProfile"])[0])
    verify("unchanged two-aircraft mission totals and schedule", len(rows(rt["MissionType"])) == len(rows(rt["OperationProfile"])) == 1 and mt["MTID"] == "BASIC-MISSION" and mt["NOS"] == mt["MNOS"] == 2 and mt["DURN"] == 2 and op["STIM"] == 8 and op["SPRID"] == "BASIC-MISSION")
    spec = {r["SID"]: r for r in (named(rt["MissionSystem"], row) for row in rows(rt["MissionSystem"]))}
    verify("exact one-per-type MissionSystem requirements", len(rows(rt["MissionSystem"])) == 2 and set(spec) == {"TEACH-AIR-01", "TEACH-AIR-02"} and all(r["MTID"] == "BASIC-MISSION" and r["NOS"] == r["MNOS"] == 1 and r["MNOSA"] is None for r in spec.values()) and spec["TEACH-AIR-01"]["PRI"] == 1 and spec["TEACH-AIR-02"]["PRI"] == 2)
    runner_text = (CASE / "run_native_ssh.ps1").read_text(errors="replace")
    verify("runner requires SSH, session0, mutex and GUI identity", all(fragment in runner_text for fragment in ("$env:SSH_CONNECTION", ".SessionId -ne 0", "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui", "source fingerprint changed during native run")))

    observed = {}
    for variant, run in RUNS.items():
        pfx = variant + ": "
        src = CASE / f"{variant}-input.json"
        inv, closure, steps = (read_json(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        expected = {"input": hash_file(src), "parent": hash_file(PARENT), "contract": hash_file(CASE / "contract.json"), "builder": hash_file(CASE / "build.py"), "checker": hash_file(CASE / "check_roundtrip.py"), "runner_script": hash_file(CASE / "run_native_ssh.ps1")}
        verify(pfx + "run copy and invocation source SHA", hash_file(run / "input.json") == expected["input"] == inv["input_sha256"])
        verify(pfx + "sealed invocation and closure identity", inv["run_id"] == closure["run_id"] == run.name and inv["variant"] == variant and closure["invocation_sha256"] == hash_file(run / "invocation.json"))
        verify(pfx + "before/after source hashes", all(inv["source_hashes_before"].get(k) == v and closure["source_hashes_before"].get(k) == v and closure["source_hashes_after"].get(k) == v for k, v in expected.items()))
        verify(pfx + "guarded SSH session0, mutex, GUI identity", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == GUI)
        raw = closure["raw"]
        verify(pfx + "all 12 raw artifact sizes and hashes", len(raw) == 12 and all((run / n).is_file() and len((run / n).read_bytes()) == rec["bytes"] and hash_file(run / n) == rec["sha256"] for n, rec in raw.items()))
        verify(pfx + "four CLI steps plus checker preserve GUI", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True for s in steps))
        verify(pfx + "planned CLI arguments match actual steps", [c["name"] for c in inv["planned_commands"]] == ["import", "export", "calc", "jsonreport"] and all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)))
        source_tables = tabmap(sources[variant])
        exported = tabmap(read_json(run / "roundtrip-raw.json"))
        verify(pfx + "every source schema and business row roundtrips", all(t["columns"] == exported[n]["columns"] and (not rows(t) or rows(t) == rows(exported[n])) for n, t in source_tables.items()))
        n_populated = sum(bool(rows(t)) for t in source_tables.values())
        verify(pfx + "populated table count and checker corroboration", n_populated == (13 if variant == "control" else 14) and read_json(run / "roundtrip-validation.json")["passed"] is True)
        runlog = (run / "run.log").read_text(errors="replace")
        verify(pfx + "zero errors, three classified warnings", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and sorted(map(int, re.findall(r"warning #(\d+)", runlog))) == [108, 126, 126] and not re.search(r"error #\d+", runlog))
        log = (run / "model.log").read_text(errors="replace")
        mission = "BASIC-MISSION,TEACH-UNIT,0,0,0"
        allocations = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission allocates system: <(TEACH-AIR-0[12],[0-9]+)>", log, re.M)
        expected_aircraft = {"TEACH-AIR-01,0", "TEACH-AIR-01,1"} if variant == "control" else {"TEACH-AIR-01,0", "TEACH-AIR-02,2"}
        verify(pfx + "exact aircraft instances allocated at hour 7", len(allocations) == 2 and {a for _, a in allocations} == expected_aircraft and {float(t) for t, _ in allocations} == {7.0})
        preparation = {}
        for phase in ("started", "ended"):
            preparation[phase] = re.findall(rf"^Time: ([0-9.]+) <(TEACH-AIR-0[12],[0-9]+)> preparation {phase}, mission: <{mission}>", log, re.M)
        verify(pfx + "preparation events have zero duration", all({aircraft for _, aircraft in preparation[phase]} == expected_aircraft and {float(time) for time, _ in preparation[phase]} == {7.0} and len(preparation[phase]) == 2 for phase in ("started", "ended")))
        starts = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission starting, duration: ([0-9.]+) : (.+)$", log, re.M)
        done = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission completed: (.+)$", log, re.M)
        success = re.findall(rf"^Time: ([0-9.]+) <{mission}> mission success:", log, re.M)
        verify(pfx + "one two-aircraft mission 8-10 and success", len(starts) == len(done) == len(success) == 1 and float(starts[0][0]) == 8 and float(starts[0][1]) == 2 and float(done[0][0]) == float(success[0]) == 10 and len(re.findall(r"mission starting,", log)) == 1)
        parse_aircraft = lambda text: set(re.findall(r"<(TEACH-AIR-0[12],[0-9]+)>", text))
        verify(pfx + "launched and returned identities equal allocated pair", parse_aircraft(starts[0][2]) == parse_aircraft(done[0][1]) == expected_aircraft and all(f"Time: 10 <{a.split(',')[0]},BASE-01,0> System arrives <{a}>" in log for a in expected_aircraft))
        verify(pfx + "third aircraft stays ready", "Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 3" in log and "Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :" in log)
        report = read_json(run / "report-raw.json", native=True)
        report_tables = tabmap(report, "report")
        summary = named(report_tables["ResultSummary"], rows(report_tables["ResultSummary"])[0])
        system = report_tables["SystemResults"]
        stock = report_tables["StockTotalResults"]
        srows = rows(system)
        verify(pfx + "72 contiguous half-hour system/stock bins", len(srows) == len(rows(stock)) == 72 and all(abs(r[2] - .5*i) < 1e-8 and abs(r[3] - .5*(i+1)) < 1e-8 for i, r in enumerate(srows)) and all(abs(r[0] - .5*i) < 1e-8 and abs(r[1] - .5*(i+1)) < 1e-8 for i, r in enumerate(rows(stock))))
        verify(pfx + "summary success and no failures or stock demand", summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(summary[k] == 1 for k in ("MTMF", "MSTF", "MSUF", "STMF")) and max(report_series(system, "NFAIL")) == 0 and max(report_series(stock, "NBO")) == 0)
        expected_occupancy = [2 if 8 <= i*.5 < 10 else 0 for i in range(72)]
        verify(pfx + "event-derived operation occupancy matches every bin", report_series(system, "NSYMO") == expected_occupancy and report_series(system, "STACC") == expected_occupancy)
        verify(pfx + "four operating aircraft-hours, terminal three ready", sum(.5*x for x in report_series(system, "NSYMO")) == 4 and report_series(system, "NSYRY")[-1] == 3 and report_series(system, "NSYMO")[-1] == 0)
        observed[variant] = {"allocated_aircraft": sorted(a for _, a in allocations), "mission_start": float(starts[0][0]), "mission_success_completion": float(success[0]), "operating_aircraft_hours": sum(.5*x for x in report_series(system, "NSYMO")), "report_sha256": hash_file(run / "report-raw.json")}

    verify("paired behavior changes only selected type identities", observed["control"]["allocated_aircraft"] == ["TEACH-AIR-01,0", "TEACH-AIR-01,1"] and observed["required"]["allocated_aircraft"] == ["TEACH-AIR-01,0", "TEACH-AIR-02,2"])
    decision = "bounded_pair_accepted" if all(c["passed"] for c in checks) else "review_failed"
    result = {
        "schema": "simlox-a11-independent-mixed-type-readonly/v1", "reviewer": "Standalone standard-library replay; no author imports or native invocation",
        "passed": all(c["passed"] for c in checks), "passed_count": sum(c["passed"] for c in checks), "failed_count": sum(not c["passed"] for c in checks),
        "failed": [c for c in checks if not c["passed"]], "checks": checks,
        "hashes": {"parent_input": hash_file(PARENT), "manual_pdf": hash_file(MANUAL), "contract": hash_file(CASE / "contract.json"), "control_input": hash_file(CASE / "control-input.json"), "required_input": hash_file(CASE / "required-input.json"), "control_report": observed["control"]["report_sha256"], "required_report": observed["required"]["report_sha256"]},
        "observed": observed, "manual_read": "Installed manual pp184,188,302-304 explains total/per-type NOS and MNOS, MissionSystem type priority, and explicit Formation override.",
        "decision": decision,
        "limits": ["One fixed two-hour mission in one explicit unit, with all three aircraft ready, no failures, and zero-duration preparation events; this demonstrates one selected type pair only.", "No inference about shortage, type choice under changed readiness, explicit Formation alternatives, MNOSA or ALOAA.", "SystemResults is aggregate; individual aircraft identities come from sealed native event log."],
    }
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"], "failed": result["failed"], "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
