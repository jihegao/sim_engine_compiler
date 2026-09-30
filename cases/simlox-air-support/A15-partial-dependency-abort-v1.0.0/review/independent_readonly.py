"""Independent standard-library replay of sealed A15 partial-abort evidence.

Reads source and raw native artifacts; writes only its own review JSON.
Does not import or execute the case builder, checker, validator, or SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
AIR = CASE.parent
OUT = HERE / "independent-readonly-2026-10-01.json"
VARIANTS = ("control-hour", "control-mission", "dependent-hour", "dependent-mission")
ACCEPTED_PARENT_CLOSURES = {
    "control": "0e9f6dda8a63b75a6ed061a03e761e04df2fba4307c63875ae0ca9919875f486",
    "dependent": "50a20c76ef4c52ed7bf4a529279dbebc304f826518b3dde43259538ec66494bd",
}
SOURCE_KEYS = {
    "contract": "contract.json", "builder": "build.py", "exact_diff": "exact-diff.json",
    "diff_checker": "describe_diff.py", "checker": "check_roundtrip.py",
    "runner_script": "run_native_ssh.ps1", "report_runner": "report_existing_sxo_ssh.ps1",
    "settings_builder": "make_report_settings.py",
}
checks = 0
failures: list[str] = []


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parsed(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    # Native SIMLOX JSON has commas before closing brackets/braces.
    return json.loads(re.sub(r",(?=\s*[}\]])", "", text))


def tables(path: Path, root: str) -> dict[str, dict]:
    return {t["name"]: t for t in parsed(path)[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for inst in table["instances"] for row in inst["rows"]]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def check_raw(directory: Path, closure: dict, label: str) -> None:
    for filename, meta in closure["raw"].items():
        path = directory / filename
        ck(path.is_file(), f"{label} raw exists {filename}")
        if path.is_file():
            ck(path.stat().st_size == meta["bytes"], f"{label} raw size {filename}")
            ck(sha(path) == meta["sha256"], f"{label} raw sha {filename}")


def expected_event(log: str, time: int, identity: str, event: str) -> bool:
    return any(line.startswith(f"Time: {time} <{identity}> {event}")
               for line in log.splitlines())


def main() -> None:
    index = parsed(CASE / "evidence-index.json")
    contract = parsed(CASE / "contract.json")
    delta = parsed(CASE / "exact-diff.json")["variants"]
    ck(index["contract_sha256"] == sha(CASE / "contract.json"), "index contract sha")
    ck(index["exact_diff_sha256"] == sha(CASE / "exact-diff.json"), "index diff sha")
    for key, filename in [("builder_sha256", "build.py"), ("native_runner_sha256", "run_native_ssh.ps1"),
                          ("report_settings_builder_sha256", "make_report_settings.py"),
                          ("report_runner_sha256", "report_existing_sxo_ssh.ps1")]:
        ck(index[key] == sha(CASE / filename), f"index {key}")
    settings = CASE / "runs" / "report-settings" / "all.sxs"
    ck(sha(settings) == index["local_report_settings_sha256"], "settings sha")
    ck(sha(CASE / "build.py") == contract["builder_sha256"], "contract builder sha")
    ck(sha(CASE / "describe_diff.py") == contract["diff_builder_sha256"], "contract diff builder sha")

    native_reports = {}
    operation_reports = {}
    native_logs = {}
    for variant in VARIANTS:
        branch, rate = variant.split("-")
        parent = AIR / "A14-continuous-end-abort-v1.0.1" / f"{branch}-input.json"
        input_file = CASE / f"{variant}-input.json"
        ptab, ctab = tables(parent, "model"), tables(input_file, "model")
        d = delta[variant]
        ck(sha(parent) == contract["parents"][branch]["sha256"] == d["parent_sha256"], f"{variant} parent sha")
        ck(sha(input_file) == contract["inputs_sha256"][variant] == d["input_sha256"], f"{variant} input sha")
        ck(len(ptab) == d["parent_table_count"] and len(ctab) == d["child_table_count"], f"{variant} table count")
        changed = {n for n in ptab.keys() & ctab.keys() if ptab[n] != ctab[n]}
        ck(changed == set(d["modified_parent_tables"]) == {"OperationParameter", "ProblemDescription"}, f"{variant} parent changes")
        ck(set(ctab) - set(ptab) == set(d["added_tables"]) == {"MissionTypeUtilization"}, f"{variant} added tables")
        ck(rows(ctab["ProblemDescription"]) == d["description"], f"{variant} description delta")
        ck(rows(ctab["OperationParameter"]) == d["operation_parameter"], f"{variant} operation delta")
        ck(rows(ctab["MissionTypeUtilization"]) == d["utilization"], f"{variant} utilization delta")
        ck(rows(ctab["MissionTypeUtilization"]) == [["EXECUTE", "TEACH-AIR-01", "KM",
             60.0 if rate == "hour" else 240.0, "1/HOUR" if rate == "hour" else "1/MISSION", None]], f"{variant} rate isolation")
        for name in ("SystemRepair", "ItemRepair", "MaterielPM", "Tasks", "TaskResource", "Resource", "ResourceAllocation", "StockAllocation"):
            ck(not rows(ctab[name]), f"{variant} empty demand table {name}")
        native = index["native_runs"][variant]
        n = CASE / "runs" / native["run_id"]
        inv, clo = parsed(n / "invocation.json"), parsed(n / "closure.json")
        ck(sha(n / "invocation.json") == native["invocation_sha256"] == clo["invocation_sha256"], f"{variant} invocation seal")
        ck(sha(n / "closure.json") == native["closure_sha256"], f"{variant} closure seal")
        check_raw(n, clo, f"{variant} native")
        ck(clo["error"] is None and inv["run_id"] == clo["run_id"] == native["run_id"], f"{variant} native identity/error")
        ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} ssh guard")
        ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} mutex")
        ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} gui")
        ck(inv["source_hashes_before"] == clo["source_hashes_before"] == clo["source_hashes_after"], f"{variant} source stable")
        for key, filename in SOURCE_KEYS.items():
            if key in inv["source_hashes_before"]:
                ck(inv["source_hashes_before"][key] == sha(CASE / filename), f"{variant} frozen {key}")
        ck(inv["input_sha256"] == native["input_sha256"] == sha(input_file), f"{variant} native source")
        steps = parsed(n / "steps.json")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
        for step in steps:
            ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"{variant} step {step['name']}")
        exported = tables(n / "roundtrip-raw.json", "model")
        populated = {name for name, t in ctab.items() if rows(t)}
        ck(len(populated) == (14 if branch == "control" else 15), f"{variant} populated source count")
        for name in populated:
            ck(name in exported and ctab[name]["columns"] == exported[name]["columns"] and rows(ctab[name]) == rows(exported[name]), f"{variant} exact roundtrip {name}")
        runlog = (n / "run.log").read_text(errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{variant} converter zero errors")
        ck("warning #108" in runlog and "warning #126" in runlog, f"{variant} known warnings")
        ck((n / "model.sxo").stat().st_size > 100000, f"{variant} valid sxo size")
        log = (n / "model.log").read_text(errors="replace")
        native_logs[variant] = (n / "model.log").read_bytes()
        support = "SUPPORT,TEACH-UNIT,0,0,0"
        execute = "EXECUTE,TEACH-UNIT,0,0,1"
        ck(expected_event(log, 8, support, "mission starting, duration: 2"), f"{variant} support launch")
        ck(expected_event(log, 8, execute, "mission starting, duration: 4"), f"{variant} execute launch")
        ck(expected_event(log, 10, support, "mission success:"), f"{variant} support success")
        if branch == "control":
            ck(expected_event(log, 12, execute, "mission success:") and expected_event(log, 12, execute, "mission completed:"), f"{variant} execute success")
            ck("mission aborted:" not in log, f"{variant} no abort")
        else:
            ck(expected_event(log, 10, execute, "mission aborted:") and expected_event(log, 10, execute, "aborted mission completed:"), f"{variant} execute abort")
            ck(not expected_event(log, 12, execute, "mission success:"), f"{variant} no execute success")
        ck("systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log, f"{variant} terminal ready two")
        nr = tables(n / "report-raw.json", "report")
        native_reports[variant] = nr
        ck(set(nr) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{variant} default report tables")

        indexed = index["report_runs"][variant]
        rdir = CASE / "runs" / indexed["run_id"]
        rinv, rclo = parsed(rdir / "invocation.json"), parsed(rdir / "closure.json")
        ck(sha(rdir / "invocation.json") == indexed["invocation_sha256"] == rclo["invocation_sha256"], f"{variant} report invocation seal")
        ck(sha(rdir / "closure.json") == indexed["closure_sha256"], f"{variant} report closure seal")
        check_raw(rdir, rclo, f"{variant} report")
        ck(rinv["run_id"] == indexed["run_id"] == rclo["run_id"] and rinv["source_run_id"] == indexed["source_run_id"] == native["run_id"], f"{variant} report identity")
        ck(rinv["session_id"] == 0 and "sshd.exe" in rinv["ssh_ancestor_names"], f"{variant} report ssh")
        ck(rinv["gui"]["pid"] == 13340 and rinv["gui"]["session_id"] == 1 and rinv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} report gui/mutex")
        ck(rinv["source_hashes"] == rclo["source_hashes"], f"{variant} report sources stable")
        ck(rinv["source_hashes"]["sxo"] == sha(n / "model.sxo") and rinv["source_hashes"]["source_closure"] == sha(n / "closure.json"), f"{variant} report parent seals")
        ck(rinv["source_hashes"]["settings"] == sha(settings) == indexed["settings_sha256"], f"{variant} report settings seal")
        ck(rinv["source_hashes"]["runner"] == sha(CASE / "report_existing_sxo_ssh.ps1") and rinv["source_hashes"]["builder"] == sha(CASE / "make_report_settings.py"), f"{variant} report helper seals")
        ck("-report -rpts " in rinv["command"] and " -rjexport " in rinv["command"] and str(settings).lower() in rinv["command"].lower(), f"{variant} explicit report settings")
        ck(rclo["exit_code"] == 0 and rclo["error"] is None, f"{variant} report exit")
        export_log = (rdir / "report-export.log").read_text(errors="replace")
        ck("Report completed" in export_log and "Export completed!" in export_log and "fallback" not in export_log.lower(), f"{variant} report no fallback")
        report = tables(rdir / "report-raw.json", "report")
        operation_reports[variant] = report
        ck(set(report) == {"ProblemDescription", "ResultSummary", "MissionOperation", "MissionOperationAccumulated", "MissionOperationTotal", "MissionOperationTotalAccumulated", "SystemResults", "StockTotalResults"}, f"{variant} custom report tables")
        for table in ("ResultSummary", "SystemResults", "StockTotalResults"):
            ck(records(report[table]) == records(nr[table]), f"{variant} default/remapped {table}")

        expected_end = 12 if branch == "control" else 10
        expected_km = 240 if branch == "control" else 120
        expected_oph = 6 if branch == "control" else 4
        sys = records(report["SystemResults"])
        stock = records(report["StockTotalResults"])
        ck(len(sys) == len(stock) == 32, f"{variant} 32 system/stock bins")
        for i, (sr, st) in enumerate(zip(sys, stock)):
            h = i / 2
            ready = 2 if h < 7 or h >= expected_end else (0 if h < 10 else 1)
            mission = 2 if 8 <= h < 10 else (1 if 10 <= h < expected_end else 0)
            prep = 2 if 7 <= h < 8 else 0
            ck((sr["STINT"], sr["ETINT"]) == (h, h + .5) and (st["STINT"], st["ETINT"]) == (h, h + .5), f"{variant} bin time {i}")
            ck((sr["NSYRY"], sr["NSYMA"], sr["NSYMO"], sr["NSYA"]) == (ready, 2 - ready, mission, 2), f"{variant} system ledger {i}")
            ck(sr["NSYMR"] == prep, f"{variant} preparation bin {i}")
            ck(sr["FTMO"] == mission / 2 and sr["STACC"] == mission, f"{variant} mission fractions {i}")
            ck(all(value in (0, None) for key, value in sr.items() if key not in
                   {"UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYA", "FTMO", "STACC"}),
               f"{variant} all other system metrics zero {i}")
            ck(st["PNB"] == 1 and all(st[x] == 0 for x in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} stock ledger {i}")
            ck(all(value in (0, None) for key, value in st.items() if key not in
                   {"STINT", "ETINT", "PNB"}), f"{variant} all stock movements zero {i}")
        summary = records(report["ResultSummary"])
        ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 16, f"{variant} summary horizon")
        factor = 1 if branch == "control" else 2 / 3
        ck(abs(summary[0]["MTMF"] - factor) < 1e-6 and abs(summary[0]["STMF"] - factor) < 1e-6, f"{variant} factors")
        for name in ("MissionOperation", "MissionOperationAccumulated"):
            rr = records(report[name])
            ck(len(rr) == 48, f"{variant} {name} 48 rows")
            km = {r["STINT"]: r["SOACC"] for r in rr if r["OPID"] == "KM"}
            oph = {r["STINT"]: r["SOACC"] for r in rr if r["OPID"] == "OPHOURS"}
            ck(set(km) == {i / 2 for i in range(16, 32)} and set(oph) == {i / 2 for i in range(32)}, f"{variant} {name} operation bins")
            ck(all(oph[i / 2] == 0 for i in range(16)), f"{variant} {name} premisson zero bins")
            for i in range(16, 32):
                h = i / 2
                active = min(max(h + .5 - 8, 0), expected_end - 8)
                if name == "MissionOperation":
                    ekm = 60 if h < expected_end else 0
                    eoph = 2 if h < 10 else (1 if h < expected_end else 0)
                else:
                    ekm = active * 60
                    eoph = min(max(h + .5 - 8, 0), 2) + min(max(h + .5 - 8, 0), expected_end - 8)
                ck(km[h] == ekm and oph[h] == eoph, f"{variant} {name} KM/OPHOURS bin {i}")
        totals = {r["OPID"]: r["SOACC"] for r in records(report["MissionOperationTotalAccumulated"])}
        avg = {r["OPID"]: r["SOACC"] for r in records(report["MissionOperationTotal"])}
        ck(totals == {"KM": expected_km, "OPHOURS": expected_oph}, f"{variant} cumulative totals")
        ck(avg == {"KM": expected_km / 16, "OPHOURS": expected_oph / 16}, f"{variant} 16h averages")
    for branch in ("control", "dependent"):
        h, m = f"{branch}-hour", f"{branch}-mission"
        parent_dir = AIR / "A14-continuous-end-abort-v1.0.1" / "runs" / f"a14-{branch}-v101-20261001-01"
        ck(sha(parent_dir / "closure.json") == ACCEPTED_PARENT_CLOSURES[branch], f"{branch} accepted parent closure")
        hs, ms = tables(CASE / f"{h}-input.json", "model"), tables(CASE / f"{m}-input.json", "model")
        ck({n for n in hs if hs[n] != ms[n]} == {"ProblemDescription", "MissionTypeUtilization"}, f"{branch} source rate isolation")
        ck(native_logs[h] == native_logs[m], f"{branch} rate log equality")
        for name in operation_reports[h]:
            if name != "ProblemDescription":
                ck(operation_reports[h][name] == operation_reports[m][name], f"{branch} report equality {name}")
        parent_log = parent_dir / "model.log"
        ck(native_logs[h] == parent_log.read_bytes(), f"{branch} accepted A14 event equality")
    for rate in ("hour", "mission"):
        control, dependent = tables(CASE / f"control-{rate}-input.json", "model"), tables(CASE / f"dependent-{rate}-input.json", "model")
        parent_control = tables(AIR / "A14-continuous-end-abort-v1.0.1" / "control-input.json", "model")
        parent_dependent = tables(AIR / "A14-continuous-end-abort-v1.0.1" / "dependent-input.json", "model")
        ck({n for n in control if n in dependent and control[n] != dependent[n]} ==
           {n for n in parent_control if n in parent_dependent and parent_control[n] != parent_dependent[n]} | {"ProblemDescription"},
           f"{rate} dependency contrast preserved")
    report = {
        "schema": "simlox-a15-partial-abort-independent-review/v1",
        "case": str(CASE), "evidence_index_sha256": sha(CASE / "evidence-index.json"),
        "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
        "check_count": checks, "failure_count": len(failures), "failures": failures,
        "observed_km": {v: 240 if v.startswith("control") else 120 for v in VARIANTS},
        "scope": "One deterministic CONTINUOUS dependency abort of EXECUTE at h10 versus full h12 completion, two UTILU rate forms, one selected unit, 16-hour horizon.",
        "limits": ["No random failure, fixed or extendable mission, suspension/resumption, other seeds, or cross-engine parity.",
                   "SOACC is unit-level abstract KM, not serial-numbered aircraft distance or physical kilometres.",
                   "Native data show equal rates in this pair; they do not establish a general per-mission proration law."],
    }
    OUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": report["passed"], "checks": checks, "failures": failures, "report": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
