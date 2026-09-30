"""Author replay of sealed four-way A15 partial-abort native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated
from build import PARENTS, PARENT_DIR, VARIANTS

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
SETTINGS_SHA = "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7"
PARENT_LOG_SHA = {"control": "d23fb97ec878134aaa926d080582e789e274ef78d6f4b7dab52351bb5fa3bc2c", "dependent": "196fbd62b6ecafbf9b9241aa94e40937b8aad98af2a39d9d224149cb3581fd43"}
NATIVE = {
    "control-hour": ("af783d787b590b186dc6bad9dec659912f5e5d2d9085a4e537c0c2df8f737edc", "a61e3234fbd103c826645173bbdd9ba3a8ed8bca29b2076356a2f61bfa29eb0a"),
    "control-mission": ("5dd963e213338949232c6ffeedc700418d4b7601cbb1d40c4221dc40e39b104b", "b81088c970cf46302062a90631df01d2c44d6b8611819926b228894c4621cf6f"),
    "dependent-hour": ("738810513abd31020f990bdc1b4d933acf295f9e08af971665c2ba2896ee58c4", "93256af2002dcfc7c44a62bcb47649f9cc57c1202407bca29c7077a1aee778c5"),
    "dependent-mission": ("5c34c31a0eeedbff876bea7c6eef0def9bb9baed99090801d88a9caf826c24c0", "0c2d534be2efb9826cb4ce4fdbcca2eb9efd19d1c4ba52531d4c429dcff6d65f"),
}
REPORT_CLOSURES = {
    "control-hour": "88dc8eaeb47832516a1026c020f1cc17449f611cda60c5b8b9a9edaa2af997ba",
    "control-mission": "372da8f6b348baeb80c5c45bc2a92f03cd3efeb0f1e4129ec7b7c7d5e317c69d",
    "dependent-hour": "ee22f7d3149105ac26c9b75e47efb1682895a7316b3a25cb4c129e2d671e4310",
    "dependent-mission": "c2cf462c2309b5a93d436f40a2a5ecda74b78ae428e3c55f2709dbed69ca04f2",
}
OP_TABLES = ("MissionOperation", "MissionOperationTotal", "MissionOperationAccumulated", "MissionOperationTotalAccumulated")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def col(table: dict, name: str) -> int:
    return [c["name"] for c in table["columns"]].index(name)


def require(ok: bool, label: str, checks: list[str]) -> None:
    if not ok:
        raise AssertionError(label)
    checks.append(label)


def sealed(run: Path, checks: list[str]) -> tuple[dict, dict]:
    closure = read(run / "closure.json")
    invocation = read(run / "invocation.json")
    require(closure["error"] is None, f"{run.name} no closure error", checks)
    require(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{run.name} invocation SHA", checks)
    for name, record in closure["raw"].items():
        path = run / name
        require(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"{run.name} sealed {name}", checks)
    return closure, invocation


def report_tables(path: Path) -> dict[str, dict]:
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def main() -> None:
    checks: list[str] = []
    contract = read(HERE / "contract.json")
    require(sha(DEFAULT) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d", "installed default settings SHA", checks)
    require(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed executable SHA", checks)
    for mode, (name, expected) in PARENTS.items():
        require(sha(PARENT_DIR / name) == expected and contract["parents"][mode]["sha256"] == expected, f"{mode} accepted parent SHA", checks)
    for key, name in (("builder_sha256", "build.py"), ("diff_builder_sha256", "describe_diff.py"), ("exact_diff_sha256", "exact-diff.json")):
        require(contract[key] == sha(HERE / name), f"contract {name} SHA", checks)
    require(sha(RUNS / "report-settings" / "all.sxs") == SETTINGS_SHA, "local operation settings SHA", checks)
    default_tables = {}
    operation_tables = {}
    for variant in VARIANTS:
        mode, rate = variant.split("-")
        input_sha = contract["inputs_sha256"][variant]
        source = HERE / f"{variant}-input.json"
        run = RUNS / f"a15-partial-{variant}-v100-20261001-01"
        sxo_sha, closure_sha = NATIVE[variant]
        require(sha(source) == input_sha and sha(run / "input.json") == input_sha, f"{variant} frozen input", checks)
        require(sha(run / "model.sxo") == sxo_sha and sha(run / "closure.json") == closure_sha, f"{variant} native SXO and closure", checks)
        closure, invocation = sealed(run, checks)
        require(invocation["variant"] == variant and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} session-0 SSH", checks)
        require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} queue/GUI provenance", checks)
        require(closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{variant} source stable and frozen contract", checks)
        steps = read(run / "steps.json")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} five guarded native steps", checks)
        roundtrip = read(run / "roundtrip-validation.json")
        expected_count = 14 if mode == "control" else 15
        require(roundtrip["passed"] and not roundtrip["differences"] and len(roundtrip["populated_tables"]) == expected_count, f"{variant} {expected_count}-table roundtrip", checks)
        original = populated(parse_native(source))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        require(all(exported.get(name) == table for name, table in original.items()), f"{variant} direct row equality", checks)
        source_tables = {t["name"]: t for t in parse_native(source)["model"]["tables"]}
        require(rows(source_tables["OperationParameter"]) == [["KM", "Abstract custom mission exposure", None]], f"{variant} custom KM", checks)
        expected_util = [["EXECUTE", "TEACH-AIR-01", "KM", 60.0 if rate == "hour" else 240.0, "1/HOUR" if rate == "hour" else "1/MISSION", None]]
        require(rows(source_tables["MissionTypeUtilization"]) == expected_util, f"{variant} one EXECUTE rate row", checks)
        no_supply_rows = ("SystemRepair", "ItemRepair", "Tasks", "TaskResource", "Resource", "ResourceAllocation", "MaterielPM", "PMLocation", "StockAllocation", "SubTaskType", "TaskBreakDown", "SubTaskResource")
        require(all(name in source_tables and not rows(source_tables[name]) for name in no_supply_rows), f"{variant} no configured repair/PM/resource/stock task rows", checks)
        require(("MissionDependence" in original) == (mode == "dependent"), f"{variant} dependence branch", checks)
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Input conversion completed. Errors: 0, Warnings: 2" in run_log and "warning #108" in run_log and "warning #126" in run_log, f"{variant} zero conversion errors", checks)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        require(sha(run / "model.log") == PARENT_LOG_SHA[mode], f"{variant} accepted A14 event log SHA", checks)
        require("Time: 8 <EXECUTE,TEACH-UNIT,0,0,1> mission starting, duration: 4" in log and "Time: 10 <SUPPORT,TEACH-UNIT,0,0,0> mission success" in log, f"{variant} simultaneous 8/10 timeline", checks)
        terminal = "mission aborted" if mode == "dependent" else "mission success"
        hour = 10 if mode == "dependent" else 12
        require(f"Time: {hour} <EXECUTE,TEACH-UNIT,0,0,1> {terminal}" in log and ("Time: 12 <EXECUTE,TEACH-UNIT,0,0,1> mission success" in log) == (mode == "control"), f"{variant} EXECUTE terminal event", checks)
        require("waiting for resource" not in log.lower() and "backorder" not in log.lower(), f"{variant} no observable resource/stock wait", checks)
        tables = report_tables(run / "report-raw.json")
        system, stock, summary = tables["SystemResults"], tables["StockTotalResults"], tables["ResultSummary"]
        sr, tr = rows(system), rows(stock)
        require(len(sr) == len(tr) == 32 and rows(summary)[0][col(summary, "RTIUP")] == 16, f"{variant} 32 half-hour bins and horizon", checks)
        require(all(r[col(system, "NSYMO")] == 2 for r in sr if 8 <= r[col(system, "STINT")] < 10), f"{variant} two operating 8-10", checks)
        require(all(r[col(system, "NSYMO")] == (0 if mode == "dependent" else 1) for r in sr if 10 <= r[col(system, "STINT")] < 12), f"{variant} post-10 operation", checks)
        require(sr[-1][col(system, "NSYRY")] == 2 and all(r[col(system, "NFAIL")] == r[col(system, "NREPT")] == r[col(system, "NPMT")] == 0 for r in sr), f"{variant} terminal ready two and zero failure/repair/PM", checks)
        require(all(r[col(stock, "NBO")] == r[col(stock, "NDF")] == 0 for r in tr), f"{variant} zero stock demand/backorder", checks)
        expected_mtmf = 1 if mode == "control" else 2 / 3
        require(abs(rows(summary)[0][col(summary, "MTMF")] - expected_mtmf) < 1e-6, f"{variant} mission time factor", checks)
        default_tables[variant] = tables

        report = RUNS / f"a15-partial-report-{variant}-v100-20261001-01"
        require(sha(report / "closure.json") == REPORT_CLOSURES[variant], f"{variant} report closure SHA", checks)
        rc, ri = sealed(report, checks)
        require(rc["exit_code"] == 0 and ri["variant"] == variant and ri["source_run_id"] == run.name, f"{variant} report provenance", checks)
        require(ri["source_hashes"] == rc["source_hashes"] and ri["source_hashes"]["sxo"] == sxo_sha and ri["source_hashes"]["source_closure"] == closure_sha, f"{variant} report source seals", checks)
        require(ri["source_hashes"]["settings"] == SETTINGS_SHA and ri["source_hashes"]["builder"] == sha(HERE / "make_report_settings.py") and ri["source_hashes"]["runner"] == sha(HERE / "report_existing_sxo_ssh.ps1"), f"{variant} settings/code seals", checks)
        require(ri["session_id"] == 0 and "sshd.exe" in ri["ssh_ancestor_names"] and ri["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and ri["gui"]["pid"] == 13340 and ri["gui"]["session_id"] == 1, f"{variant} guarded report context", checks)
        report_log = (report / "report-export.log").read_text(encoding="utf-8-sig")
        require("Report completed" in report_log and "Export completed" in report_log and "Reverting to default settings" not in report_log and "could not be loaded" not in report_log, f"{variant} no report-settings fallback", checks)
        ops = report_tables(report / "report-raw.json")
        require(all(n in ops and "SOACC" in [c["name"] for c in ops[n]["columns"]] for n in OP_TABLES), f"{variant} four SOACC tables", checks)
        for name in OP_TABLES:
            require(all(row[0] == "Total over all Units" for row in rows(ops[name])), f"{variant} {name} all-unit label", checks)
        expected_km = 240 if mode == "control" else 120
        total_acc = [r for r in rows(ops["MissionOperationTotalAccumulated"]) if r[col(ops["MissionOperationTotalAccumulated"], "OPID")] == "KM"]
        total_avg = [r for r in rows(ops["MissionOperationTotal"]) if r[col(ops["MissionOperationTotal"], "OPID")] == "KM"]
        require(len(total_acc) == 1 and total_acc[0][-1] == expected_km and len(total_avg) == 1 and abs(total_avg[0][-1] - expected_km / 16) < 1e-6, f"{variant} {expected_km} KM accumulated and horizon average", checks)
        km = [r for r in rows(ops["MissionOperation"]) if r[col(ops["MissionOperation"], "OPID")] == "KM"]
        cumulative = [r for r in rows(ops["MissionOperationAccumulated"]) if r[col(ops["MissionOperationAccumulated"], "OPID")] == "KM"]
        require(len(km) == len(cumulative) == 16 and [r[-1] for r in km if 8 <= r[3] < (12 if mode == "control" else 10)] == [60] * (8 if mode == "control" else 4), f"{variant} active half-hour KM rate", checks)
        require([r[-1] for r in cumulative if 8 <= r[3] < (12 if mode == "control" else 10)] == [30 * i for i in range(1, (8 if mode == "control" else 4) + 1)], f"{variant} active cumulative KM", checks)
        require(all(r[-1] == 0 for r in km if r[3] >= (12 if mode == "control" else 10)) and cumulative[-1][-1] == expected_km, f"{variant} post-operation KM plateau", checks)
        operation_tables[variant] = ops
    for mode in PARENTS:
        hour, mission = f"{mode}-hour", f"{mode}-mission"
        require(rows(default_tables[hour]["SystemResults"]) == rows(default_tables[mission]["SystemResults"]) and rows(default_tables[hour]["StockTotalResults"]) == rows(default_tables[mission]["StockTotalResults"]), f"{mode} rate form preserves default ledgers", checks)
        require(all(rows(operation_tables[hour][name]) == rows(operation_tables[mission][name]) for name in OP_TABLES), f"{mode} rate form preserves SOACC tables", checks)
    result = {
        "schema": "simlox-a15-partial-dependency-abort-author-validation/v1",
        "decision": "GO_bounded_continuous_dependency_abort_KM_exposure",
        "check_count": len(checks),
        "checks": checks,
        "limits": ["one deterministic CONTINUOUS dependency abort", "all-unit report with only EXECUTE assigned KM", "not shared-formation serial-aircraft disaggregation", "failure/PM and physical kilometres unverified"],
    }
    output = HERE / "author-validation-2026-10-01.json"
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"decision": result["decision"], "check_count": len(checks), "report_sha256": sha(output)}))


if __name__ == "__main__":
    main()
