"""Replay sealed J07.var05 unit/group/type CLI evidence without native execution."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "runs" / "j07-unit-type-v100-20261001-01"
REPORTS = HERE / "runs" / "report-settings"
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0"
PARENT_RUN = PARENT / "runs" / "a17-v100-ssh-20260929-01"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
CHILD_SXO_SHA = "fd0ed37f117fcc497621a363407e6e96f36930a00b58c5e03ca038757b5dc445"
PARENT_SXO_SHA = "f4c2fcd42c5620ec6e7adf163962bb6001a4a9acf49eee8d7adfeba50113349b"
SELECTORS = ("all", "group", "unit-a", "unit-b", "type-a", "type-b", "group-type-a", "group-type-b")
CHECKS: list[str] = []


def check(condition: bool, name: str) -> None:
    if not condition:
        raise AssertionError(name)
    CHECKS.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native writer's trailing commas are normalized in memory only.
        return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def report_tables(path: Path) -> dict[str, tuple[list[str], list[dict]]]:
    result = {}
    for table in native_json(path)["report"]["tables"]:
        names = [c["name"] for c in table["columns"]]
        rows = [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]
        check(table["name"] not in result, f"unique report table {path.parent.name}/{table['name']}")
        result[table["name"]] = (names, rows)
    return result


def rows(tables: dict, name: str) -> list[dict]:
    return tables[name][1] if name in tables else []


def near(actual: float, expected: float, label: str) -> None:
    check(actual is not None and math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-7), label)


def verify_closure(run: Path, *, report_only: bool) -> tuple[dict, dict]:
    closure = source(run / "closure.json")
    invocation = source(run / "invocation.json")
    check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{run.name} invocation seal")
    for name, detail in closure["raw"].items():
        file = run / name
        check(file.is_file() and file.stat().st_size == detail["bytes"] and sha(file) == detail["sha256"], f"{run.name} raw seal {name}")
    check(invocation["gui_pid"] == 13340 if report_only else invocation["gui"]["pid"] == 13340, f"{run.name} GUI PID")
    check(invocation["gui_session"] == 1 if report_only else invocation["gui"]["session_id"] == 1, f"{run.name} GUI session")
    check("sshd.exe" in invocation["ssh_ancestors"] if report_only else "sshd.exe" in invocation["ssh_ancestor_names"], f"{run.name} SSH ancestor")
    if report_only:
        check(closure["exit_code"] == 0, f"{run.name} report exit")
        check(closure["runner_sha256"] == invocation["runner_sha256"], f"{run.name} runner seal")
        check(closure["settings_sha256"] == invocation["settings_sha256"], f"{run.name} settings seal")
        check(invocation["installed_default_sha256"] == DEFAULT_SHA, f"{run.name} default settings")
    else:
        check(closure["error"] is None, "native closure has no error")
        check(closure["source_hashes_before"] == closure["source_hashes_after"], "native source hashes stable")
        steps = source(run / "steps.json")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
        check(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native steps passed and GUI preserved")
    return closure, invocation


def check_fixed(tables: dict, unit: str, mission: str, planned: int, mission_hours: float, system_hours: float, label: str) -> None:
    fixed = rows(tables, "FixedMissionResultsTotal")
    check(len(fixed) == 1, f"{label} one fixed total row")
    row = fixed[0]
    check((row["UNID"], row["MTID"]) == (unit, mission), f"{label} selector names")
    for field in ("NMREQ", "NMSTA", "NMSUC"):
        near(row[field], planned, f"{label} {field}")
    for field in ("MTREQ", "MTACC"):
        near(row[field], mission_hours, f"{label} {field}")
    for field in ("STREQ", "STACC"):
        near(row[field], system_hours, f"{label} {field}")
    for field in ("MTF", "FMSTA", "FMSUC", "STF"):
        near(row[field], 1, f"{label} {field}")
    total = rows(tables, "MissionResultsTotal")
    check(len(total) == 1 and (total[0]["UNID"], total[0]["MTID"]) == (unit, mission), f"{label} mission total identity")
    near(total[0]["MTREQ"], mission_hours / 36, f"{label} mean mission demand")
    near(total[0]["MTACC"], mission_hours / 36, f"{label} mean mission accomplishment")
    near(total[0]["STREQ"], system_hours / 36, f"{label} mean system demand")
    near(total[0]["STACC"], system_hours / 36, f"{label} mean system accomplishment")
    series = rows(tables, "MissionResults")
    check(len(series) == 72, f"{label} 72 half-hour mission bins")
    for field, expected in (("MTREQ", mission_hours), ("MTACC", mission_hours), ("STREQ", system_hours), ("STACC", system_hours)):
        near(sum(r[field] * (r["ETINT"] - r["STINT"]) for r in series), expected, f"{label} integrated {field}")


def main() -> dict:
    check(sha(DEFAULT) == DEFAULT_SHA, "installed report settings unchanged")
    contract = source(HERE / "contract.json")
    child = source(HERE / "native-input.json")
    parent = source(PARENT / "native-input.json")
    check(sha(HERE / "native-input.json") == contract["input_sha256"], "child input fingerprint")
    check(sha(PARENT / "native-input.json") == contract["parent_input_sha256"], "parent input fingerprint")
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    check(before.keys() == after.keys(), "same source table names")
    check({name for name in before if before[name] != after[name]} == {"ProblemDescription", "MissionType", "OperationProfile", "Operations"}, "four-table source delta")
    check(source(HERE / "exact-diff.json")["changed_tables"] == {name: {"before": before[name]["instances"][0]["rows"], "after": after[name]["instances"][0]["rows"]} for name in before if before[name] != after[name]}, "exact diff artifact")
    native_closure, native_invocation = verify_closure(NATIVE, report_only=False)
    check(sha(NATIVE / "model.sxo") == CHILD_SXO_SHA, "child sxo fingerprint")
    check(sha(PARENT_RUN / "model.sxo") == PARENT_SXO_SHA, "A17 sxo fingerprint")
    check(native_invocation["input_sha256"] == contract["input_sha256"], "native input identity")
    check(source(NATIVE / "roundtrip-validation.json")["passed"], "business source roundtrip")
    runlog = (NATIVE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("Errors: 0, Warnings: 2, Notes: 0" in runlog and runlog.count("warning #108") == 1 and runlog.count("warning #126") == 1, "zero conversion errors and expected warnings")
    eventlog = (NATIVE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for mission, unit, system in (("MISSION-A", "TEACH-UNIT", 0), ("MISSION-B", "TEACH-UNIT-2", 1)):
        prefix = f"<{mission},{unit},0,0,"
        for time, phrase in ((7, "mission created"), (8, "mission starting, duration: 2"), (10, "mission success"), (10, "mission completed")):
            check(any(line.startswith(f"Time: {time} {prefix}") and phrase in line for line in eventlog.splitlines()), f"{mission} event {time} {phrase}")
        check(f"mission allocates system: <TEACH-AIR-01,{system}>" in eventlog, f"{mission} aircraft assignment")
        check(f"Time: 10 <{unit} at <BASE-0{system+1},0>> systems ready: 1 :<TEACH-AIR-01,{system}>" in eventlog, f"{mission} terminal readiness")
    check(eventlog.count("mission starting, duration: 2") == 2 and eventlog.count("mission success:") == 2, "two sorties and two successes")
    default_report = report_tables(NATIVE / "report-raw.json")
    summary = rows(default_report, "ResultSummary")
    check(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36, "global summary horizon")
    for field in ("MTMF", "MSTF", "MSUF", "STMF"):
        near(summary[0][field], 1, f"global {field}")
    system = rows(default_report, "SystemResults")
    stock = rows(default_report, "StockTotalResults")
    check(len(system) == len(stock) == 72, "72 System and Stock bins")
    for i, (sy, st) in enumerate(zip(system, stock)):
        near(sy["STINT"], i / 2, f"system bin {i} start")
        near(sy["ETINT"], (i + 1) / 2, f"system bin {i} end")
        near(st["STINT"], i / 2, f"stock bin {i} start")
        near(st["ETINT"], (i + 1) / 2, f"stock bin {i} end")
        near(sy["NSYMO"], 2 if 16 <= i < 20 else 0, f"system bin {i} mission operating")
        near(st["PNB"], 1, f"stock bin {i} no backorders")
    near(system[-1]["NSYRY"], 2, "two aircraft ready at end")

    expected = {
        "all": ("Total over all Units", "Total over all Missions", 2, 4, 4),
        "unit-a": ("TEACH-UNIT", "Total over all Missions", 1, 2, 2),
        "unit-b": ("TEACH-UNIT-2", "Total over all Missions", 1, 2, 2),
        "type-a": ("Total over all Units", "MISSION-A", 1, 2, 2),
        "type-b": ("Total over all Units", "MISSION-B", 1, 2, 2),
    }
    report_sha = {}
    for selector in SELECTORS:
        run = REPORTS / f"j07-{selector}-report-20261001-01"
        closure, invocation = verify_closure(run, report_only=True)
        check(invocation["selector"] == selector and closure["source_sxo_sha256"] == CHILD_SXO_SHA, f"child report {selector} source and selector")
        check(invocation["runner_sha256"] == sha(HERE / "report_existing_sxo_ssh.ps1"), f"child report {selector} runner fingerprint")
        check(invocation["settings_sha256"] == sha(REPORTS / f"{selector}.sxs"), f"child report {selector} settings fingerprint")
        tables = report_tables(run / "report-raw.json")
        report_sha[selector] = sha(run / "report-raw.json")
        if selector in expected:
            check_fixed(tables, *expected[selector], f"child {selector}")
        else:
            check(not any("Mission" in name for name in tables), f"child {selector} no group-owned mission rows")

    for selector in ("all", "group", "unit-a", "unit-b"):
        run = REPORTS / f"a17-{selector}-report-20261001-01"
        closure, invocation = verify_closure(run, report_only=True)
        check(invocation["selector"] == selector and closure["source_sxo_sha256"] == PARENT_SXO_SHA, f"A17 report {selector} source and selector")
        check(invocation["runner_sha256"] == sha(HERE / "report_group_parent_ssh.ps1"), f"A17 report {selector} runner fingerprint")
        check(invocation["settings_sha256"] == sha(REPORTS / f"{selector}.sxs"), f"A17 report {selector} settings fingerprint")
        tables = report_tables(run / "report-raw.json")
        if selector in ("all", "group"):
            unit = "Total over all Units" if selector == "all" else "TEACH-GROUP"
            check_fixed(tables, unit, "Total over all Missions", 1, 2, 4, f"A17 {selector}")
        else:
            check(not any("Mission" in name for name in tables), f"A17 {selector} no unit-owned mission rows")

    check(report_sha["all"] != report_sha["unit-a"] and report_sha["unit-a"] != report_sha["unit-b"], "distinct native selector reports")
    return {"schema": "simlox-j07-var05-unit-type-author-validation/v1", "passed": True, "contract_status": "bounded_unit_type_go", "checks": len(CHECKS), "differences": [], "native_run": NATIVE.name, "report_runs": [f"j07-{s}-report-20261001-01" for s in SELECTORS] + [f"a17-{s}-report-20261001-01" for s in ("all", "group", "unit-a", "unit-b")], "scope": "Two unit-owned one-aircraft fixed missions of different types: per-unit and per-type native rows add to the all-unit result. A group membership selector has no child mission rows; an A17 group-owned mission has a group row and no member-unit mission rows. One seed, one 36-hour horizon, report-only local settings.", "limitations": ["Group membership alone did not produce an aggregate of member-unit missions; do not claim it does.", "Regenerative denominator, mid-mission partial outcomes, GUI rendering, and cross-engine parity are unverified."]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        result = {"schema": "simlox-j07-var05-unit-type-author-validation/v1", "passed": False, "checks": len(CHECKS), "differences": [f"{type(exc).__name__}: {exc}"]}
    output = HERE / "review" / "author-validation-2026-10-01.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
