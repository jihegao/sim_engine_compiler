"""Read-only replay of J07 fixed/regenerative denominator native evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "runs" / "j07-fixed-regen-v100-20261001-01"
REPORT_ROOT = HERE / "runs" / "report-settings"
PARENT = HERE.parent / "A07-regenerative-relief-v1.0.0"
PARENT_RUN = PARENT / "runs" / "a07-regenerative-relief-v100-ssh-20260930-01"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
CHILD_SXO_SHA = "be3e180ffaa2b668a07a03a1a4cbc4b428ce35aa2b0e696fca30daff41da53de"
PARENT_SXO_SHA = "1b8284cfcedbe80eefbecc6ffb9f4b8351a4fbe6618851bca59699367b0fec4e"
CHILD_SELECTORS = ("all", "regenerative", "fixed-ok", "fixed-deny")
PARENT_SELECTORS = ("all", "regenerative")
CHECKS: list[str] = []


def ck(ok: bool, label: str) -> None:
    if not ok:
        raise AssertionError(label)
    CHECKS.append(label)


def near(actual: float, expected: float, label: str, tolerance: float = 1e-6) -> None:
    ck(actual is not None and math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Keep source bytes sealed; normalize native trailing commas in memory.
        return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(path: Path) -> dict[str, list[dict]]:
    result = {}
    for table in native(path)["report"]["tables"]:
        names = [c["name"] for c in table["columns"]]
        ck(table["name"] not in result, f"unique table {path.parent.name}/{table['name']}")
        result[table["name"]] = [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]
    return result


def seal(run: Path, report_only: bool) -> tuple[dict, dict]:
    closure, invocation = plain(run / "closure.json"), plain(run / "invocation.json")
    ck(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{run.name} invocation seal")
    for name, record in closure["raw"].items():
        path = run / name
        ck(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"{run.name} raw seal {name}")
    if report_only:
        ck(closure["exit_code"] == 0 and closure["runner_sha256"] == invocation["runner_sha256"], f"{run.name} report exit/runner")
        ck(closure["settings_sha256"] == invocation["settings_sha256"], f"{run.name} settings seal")
        ck(invocation["installed_default_sha256"] == DEFAULT_SHA, f"{run.name} default fingerprint")
        ck(invocation["gui_pid"] == 13340 and invocation["gui_session"] == 1 and "sshd.exe" in invocation["ssh_ancestors"], f"{run.name} GUI/SSH")
    else:
        ck(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "native closure success/stability")
        ck(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and "sshd.exe" in invocation["ssh_ancestor_names"], "native GUI/SSH")
        steps = plain(run / "steps.json")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
        ck(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native five steps completed")
    return closure, invocation


def business(path: Path) -> dict:
    result = {}
    for table in native(path)["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            result[table["name"]] = {"columns": table["columns"], "rows": rows}
    return result


def fixed_row(report: dict, mission: str, counts: tuple[int, int, int], mission_hours: tuple[int, int], system_hours: tuple[int, int]) -> None:
    rows = report.get("FixedMissionResultsTotal", [])
    ck(len(rows) == 1, f"{mission} one fixed-total row")
    row = rows[0]
    ck(row["MTID"] == mission, f"{mission} selected identity")
    for field, expected in zip(("NMREQ", "NMSTA", "NMSUC"), counts):
        near(row[field], expected, f"{mission} {field}")
    for field, expected in zip(("MTREQ", "MTACC"), mission_hours):
        near(row[field], expected, f"{mission} {field}")
    for field, expected in zip(("STREQ", "STACC"), system_hours):
        near(row[field], expected, f"{mission} {field}")
    near(row["FMSTA"], counts[1] / counts[0], f"{mission} FMSTA")
    near(row["FMSUC"], counts[2] / counts[0], f"{mission} FMSUC")


def main() -> dict:
    contract = plain(HERE / "contract.json")
    ck(sha(HERE / "native-input.json") == contract["input_sha256"], "frozen child source")
    ck(sha(PARENT / "native-input.json") == contract["parent_input_sha256"], "accepted A07 source")
    ck(sha(DEFAULT) == DEFAULT_SHA, "installed default settings unchanged")
    before = {t["name"]: t for t in plain(PARENT / "native-input.json")["model"]["tables"]}
    after = {t["name"]: t for t in plain(HERE / "native-input.json")["model"]["tables"]}
    ck(before.keys() == after.keys() and {n for n in before if before[n] != after[n]} == {"ProblemDescription", "MissionType", "OperationProfile"}, "three-table parent delta")
    diff = plain(HERE / "exact-diff.json")
    ck(diff["changed_tables"] == {n: {"before": before[n]["instances"][0]["rows"], "after": after[n]["instances"][0]["rows"]} for n in before if before[n] != after[n]}, "exact diff artifact")
    source_business, export_business = business(NATIVE / "input.json"), business(NATIVE / "roundtrip-raw.json")
    ck(len(source_business) == 13, "13 populated source tables")
    for name, table in source_business.items():
        ck(export_business[name] == table, f"business roundtrip {name}")
    closure, invocation = seal(NATIVE, False)
    ck(invocation["input_sha256"] == contract["input_sha256"], "native input fingerprint")
    ck(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), "pre-run contract seal")
    ck(sha(NATIVE / "model.sxo") == CHILD_SXO_SHA and sha(PARENT_RUN / "model.sxo") == PARENT_SXO_SHA, "child/A07 SXO fingerprints")
    ck(plain(NATIVE / "roundtrip-validation.json")["passed"], "native source checker")
    runlog = (NATIVE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Errors: 0, Warnings: 2, Notes: 0" in runlog and runlog.count("warning #108") == 1 and runlog.count("warning #126") == 1, "zero errors/known warnings")
    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for start, end, index in ((8, 12, 0), (10, 14, 1), (12, 16, 2), (14, 16, 3)):
        prefix = f"<BASIC-MISSION,TEACH-UNIT,0,{index},{index}>"
        ck(f"Time: {start} {prefix} mission starting, duration: 4" in log, f"regen child {index} start")
        ck(f"Time: {end} {prefix} mission success:" in log and f"Time: {end} {prefix} mission completed:" in log, f"regen child {index} success/end")
    for time, mission, phrase in ((20, "FIXED-OK", "mission starting, duration: 4"), (24, "FIXED-OK", "mission success:"), (24, "FIXED-OK", "mission completed:"), (27, "FIXED-DENY", "mission activated, systems requested: 3"), (28.3333, "FIXED-DENY", "mission cancelled:")):
        ck(any(line.startswith(f"Time: {time} <{mission},") and phrase in line for line in log.splitlines()), f"{mission} {phrase} at {time}")
    ck(log.count("mission starting, duration: 4") == 5 and log.count("mission success:") == 5 and log.count("mission cancelled:") == 1, "five starts/successes and one denial")
    default = tables(NATIVE / "report-raw.json")
    parent_default = tables(PARENT_RUN / "report-raw.json")
    summary = default["ResultSummary"]
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36, "summary horizon")
    for field, expected in (("MSTF", .5), ("MSUF", .5), ("MTMF", .75), ("STMF", 18 / 28)):
        near(summary[0][field], expected, f"summary {field}")
    parent_summary = parent_default["ResultSummary"]
    ck(len(parent_summary) == 1, "A07 one summary row")
    for field, expected in (("MSTF", 0), ("MSUF", 0), ("MTMF", 1), ("STMF", 14 / 12)):
        near(parent_summary[0][field], expected, f"A07 summary {field}")
    system, stock = default["SystemResults"], default["StockTotalResults"]
    ck(len(system) == len(stock) == 72, "72 System and Stock bins")
    parent_system, parent_stock = parent_default["SystemResults"], parent_default["StockTotalResults"]
    ck(len(parent_system) == len(parent_stock) == 72 and stock == parent_stock, "A07 control has same stock ledger")
    for i, (sy, st) in enumerate(zip(system, stock)):
        near(sy["STINT"], i / 2, f"System interval {i} start")
        near(sy["ETINT"], (i + 1) / 2, f"System interval {i} end")
        near(st["STINT"], i / 2, f"Stock interval {i} start")
        near(st["ETINT"], (i + 1) / 2, f"Stock interval {i} end")
        near(st["NBO"], 0, f"Stock interval {i} no backorders")
        near(st["PNB"], 1, f"Stock interval {i} no-backorder fraction")
        near(sy["NFAIL"], 0, f"System interval {i} no failures")
        near(sy["NREPT"], 0, f"System interval {i} no repairs")
        near(sy["NSYMO"], parent_system[i]["NSYMO"] + (1 if 40 <= i < 48 else 0), f"A07 plus fixed operation interval {i}")
        if 40 <= i < 48:
            near(sy["NSYMO"], 1, f"fixed operating interval {i}")
        if 54 <= i < 57:
            near(sy["NSYMO"], 0, f"denied demand no operation interval {i}")
    near(sum(r["NSYMO"] * .5 for r in system), 18, "18 aircraft operation hours")
    near(system[-1]["NSYRY"], 2, "two aircraft ready at end")

    reports = {}
    for source, selectors, sxo, runner in (("j07", CHILD_SELECTORS, CHILD_SXO_SHA, "report_existing_sxo_ssh.ps1"), ("a07", PARENT_SELECTORS, PARENT_SXO_SHA, "report_a07_parent_ssh.ps1")):
        for selector in selectors:
            run = REPORT_ROOT / f"{source}-{selector}-report-20261001-01"
            report_closure, report_invocation = seal(run, True)
            ck(report_invocation["selector"] == selector and report_closure["source_sxo_sha256"] == sxo, f"{source}/{selector} source/selector")
            ck(report_invocation["runner_sha256"] == sha(HERE / runner), f"{source}/{selector} runner fingerprint")
            ck(report_invocation["settings_sha256"] == sha(REPORT_ROOT / f"{selector}.sxs"), f"{source}/{selector} settings fingerprint")
            reports[f"{source}-{selector}"] = tables(run / "report-raw.json")
    fixed_row(reports["j07-all"], "Total over all Missions", (2, 1, 1), (8, 4), (16, 4))
    fixed_row(reports["j07-fixed-ok"], "FIXED-OK", (1, 1, 1), (4, 4), (4, 4))
    fixed_row(reports["j07-fixed-deny"], "FIXED-DENY", (1, 0, 0), (4, 0), (12, 0))
    for key in ("j07-all", "j07-regenerative", "a07-all", "a07-regenerative"):
        regen = reports[key].get("RegenMissionResultsTotal", [])
        ck(len(regen) == 1, f"{key} one regenerative total")
        for field, value in (("NMSTA", 4), ("NMSUC", 4), ("MTREQ", 8), ("MTACC", 8), ("STREQ", 12), ("STACC", 14)):
            near(regen[0][field], value, f"{key} {field}")
        ck(regen[0]["NMREQ"] is None, f"{key} undefined regen fixed count")
    ck("FixedMissionResultsTotal" not in reports["a07-all"], "A07 regen-only has no fixed total")
    ck("FixedMissionResultsTotal" not in reports["j07-regenerative"], "regen type selection has no fixed total")
    ck("RegenMissionResultsTotal" not in reports["j07-fixed-ok"] and "RegenMissionResultsTotal" not in reports["j07-fixed-deny"], "fixed type selections have no regen total")
    all_rate = reports["j07-all"]["MissionResultsTotal"][0]
    for field, numerator in (("MTREQ", 16), ("MTACC", 12), ("STREQ", 28), ("STACC", 18)):
        near(all_rate[field], numerator / 36, f"all mission time rate {field}")
    return {"schema": "simlox-j07-fixed-regenerative-author-validation/v1", "passed": True, "checks": len(CHECKS), "differences": [], "native_run": NATIVE.name, "report_runs": [f"{src}-{sel}-report-20261001-01" for src, sels in (("j07", CHILD_SELECTORS), ("a07", PARENT_SELECTORS)) for sel in sels], "scope": "Four successful regenerative children, one successful fixed wave, one cancelled three-aircraft fixed demand; fixed-only native NMREQ2/NMSTA1/NMSUC1 and global MSTF/MSUF0.5, while regenerative NMSTA/NMSUC4 with NMREQ null. MTMF12/16 and STMF18/28 include regenerative operation.", "limitations": ["One deterministic seed with no failures or support-resource competition.", "Regenerative child-count behavior under failures, partial mid-mission outcomes, GUI and cross-engine behavior remain unverified."]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        result = {"schema": "simlox-j07-fixed-regenerative-author-validation/v1", "passed": False, "checks": len(CHECKS), "differences": [f"{type(exc).__name__}: {exc}"]}
    output = HERE / "review" / "author-validation-2026-10-01.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
