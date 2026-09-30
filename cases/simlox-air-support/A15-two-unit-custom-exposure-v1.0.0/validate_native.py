"""Read-only author replay of sealed A15 two-unit native and report evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J07-unit-type-report-v1.0.0" / "native-input.json"
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUNS = HERE / "runs"
VARIANTS = {
    "a": ("a-hour-b-mission", "a15-two-unit-swap-a-v100-20261001-01", "a236ee5e6f5faf7cfe6f48174e471e00c92beafe823152f265d3f8c0ae139e19", "7347162aaff3c017b66da2b8b4d7d653db7d7ab1b7c1e0d9814bb10b145c372e", "38fce23f882537c809bef906dd134b76e16c6c86d4f35c8f2d24eb3cd6ddfd27"),
    "b": ("a-mission-b-hour", "a15-two-unit-swap-b-v100-20261001-01", "696951bf181ad582bc21af5de9822232a362c88a4bb95ee25e24c1f8d836c9f5", "7bed452f7eb37ba236d616263fc9529241be83fd65f12d04147bc574e9ae1831", "dca1b507376db23c7300347f0576838ce7317a9049c20844d96067b42df1279b"),
}
SETTINGS = {
    "all": ("Total over all Units", "c2f9862c89f2aae0200d8f7a4f16a2e21b7c6ff896b42548c41b98e673f3f9b7", 240),
    "unit-a": ("TEACH-UNIT", "aa88c6dfd319640a577fe345933a8bf143bd215fe6514ed915593d5504b12d39", 120),
    "unit-b": ("TEACH-UNIT-2", "05074aed026f1c32c8a76992a4fc03dbf222776128a6910dc9b4664bff88ffd4", 120),
}
OPERATION_TABLES = ("MissionOperation", "MissionOperationTotal", "MissionOperationAccumulated", "MissionOperationTotalAccumulated")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def col(table: dict, name: str) -> int:
    return [c["name"] for c in table["columns"]].index(name)


def require(value: bool, label: str, checks: list[str]) -> None:
    if not value:
        raise AssertionError(label)
    checks.append(label)


def sealed(run: Path, closure: dict, checks: list[str]) -> None:
    require(closure["error"] is None, f"{run.name} closure error null", checks)
    require(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{run.name} invocation hash", checks)
    for name, record in closure["raw"].items():
        path = run / name
        require(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"{run.name} sealed {name}", checks)


def main() -> None:
    checks: list[str] = []
    require(sha(PARENT) == "5609881f54c47c024b1b41f338bf0dd0e04e20e49a41d42b1a81642bdab54f55", "accepted J07 parent SHA", checks)
    require(sha(DEFAULT) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d", "installed Default.sxs SHA", checks)
    require(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed executable SHA", checks)
    contract = read(HERE / "contract.json")
    require(contract["parent_input_sha256"] == sha(PARENT), "contract parent SHA", checks)
    require(contract["builder_sha256"] == sha(HERE / "build.py"), "contract builder SHA", checks)
    require(contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"), "contract exact diff SHA", checks)
    require(contract["diff_builder_sha256"] == sha(HERE / "describe_diff.py"), "contract diff builder SHA", checks)
    native_tables = {}
    for tag, (variant, source_id, input_sha, sxo_sha, closure_sha) in VARIANTS.items():
        source = HERE / f"{variant}-input.json"
        run = RUNS / source_id
        require(sha(source) == input_sha and contract["input_sha256"][variant] == input_sha, f"{tag} frozen input SHA", checks)
        require(sha(run / "input.json") == input_sha and sha(run / "model.sxo") == sxo_sha, f"{tag} native input/SXO SHA", checks)
        require(sha(run / "closure.json") == closure_sha, f"{tag} native closure SHA", checks)
        closure = read(run / "closure.json")
        invocation = read(run / "invocation.json")
        sealed(run, closure, checks)
        require(invocation["variant"] == variant and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{tag} session-0 SSH", checks)
        require(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{tag} GUI and queue guard", checks)
        require(closure["source_hashes_before"] == closure["source_hashes_after"], f"{tag} source unchanged during native run", checks)
        require(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{tag} native contract hash", checks)
        steps = read(run / "steps.json")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{tag} native step order", checks)
        require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{tag} five native steps passed", checks)
        roundtrip = read(run / "roundtrip-validation.json")
        require(roundtrip["passed"] and len(roundtrip["populated_tables"]) == 16 and not roundtrip["differences"], f"{tag} 16 source-table roundtrip", checks)
        original = populated(parse_native(source))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        require(all(exported.get(name) == table for name, table in original.items()), f"{tag} direct source row equality", checks)
        source_tables = {t["name"]: t for t in parse_native(source)["model"]["tables"]}
        require(rows(source_tables["OperationParameter"]) == [["KM", "Abstract custom mission exposure", None]], f"{tag} custom operation parameter", checks)
        expected_utilization = [["MISSION-A", "TEACH-AIR-01", "KM", 60.0, "1/HOUR", None], ["MISSION-B", "TEACH-AIR-01", "KM", 120.0, "1/MISSION", None]] if tag == "a" else [["MISSION-A", "TEACH-AIR-01", "KM", 120.0, "1/MISSION", None], ["MISSION-B", "TEACH-AIR-01", "KM", 60.0, "1/HOUR", None]]
        require(rows(source_tables["MissionTypeUtilization"]) == expected_utilization, f"{tag} frozen swapped rate rows", checks)
        require(all(not rows(source_tables[name]) for name in ("Tasks", "TaskResource", "Resource", "ResourceAllocation", "StockAllocation", "SubTaskResource")), f"{tag} no configured task-resource or stock demand", checks)
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Input conversion completed. Errors: 0, Warnings: 2" in run_log and "warning #108" in run_log and "warning #126" in run_log, f"{tag} zero conversion errors and known warnings", checks)
        model_log = (run / "model.log").read_text(encoding="utf-8-sig")
        require("waiting for resource" not in model_log.lower() and "backorder" not in model_log.lower(), f"{tag} no observable resource or stock wait", checks)
        require(sha(run / "model.log") == "a9435218c4092ecc0b55575c5619ffe5ebba38cf306c91e4090cfc0fed951648", f"{tag} accepted J07 event timeline SHA", checks)
        for mission, unit, system in (("MISSION-A", "TEACH-UNIT", 0), ("MISSION-B", "TEACH-UNIT-2", 1)):
            require(f"Time: 7 <{unit}> mission ordered: {mission}" in model_log and f"Time: 8 <{mission},{unit},0,0,{system}> mission starting, duration: 2" in model_log and f"Time: 10 <{mission},{unit},0,0,{system}> mission success" in model_log and f"Time: 10 <{mission},{unit},0,0,{system}> mission completed: <TEACH-AIR-01,{system}>" in model_log, f"{tag} {mission} 7/8/10 event chain", checks)
        default_tables = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
        system = default_tables["SystemResults"]
        stock = default_tables["StockTotalResults"]
        summary = rows(default_tables["ResultSummary"])[0]
        require(len(rows(system)) == len(rows(stock)) == 72 and summary[col(default_tables["ResultSummary"], "MTMF")] == 1, f"{tag} 72 bins and full mission factor", checks)
        require(all(r[col(system, "NSYMO")] == 2 for r in rows(system) if 8 <= r[col(system, "STINT")] < 10), f"{tag} two operating aircraft during 8-10", checks)
        require(rows(system)[-1][col(system, "NSYRY")] == 2, f"{tag} two ready aircraft at 36", checks)
        require(all(r[col(system, "NFAIL")] == 0 and r[col(system, "NREPT")] == 0 for r in rows(system)), f"{tag} zero failures and repairs", checks)
        require(all(r[col(stock, "NBO")] == 0 and r[col(stock, "NDF")] == 0 for r in rows(stock)), f"{tag} zero backorders and stock demand", checks)
        native_tables[tag] = default_tables
    require(rows(native_tables["a"]["SystemResults"]) == rows(native_tables["b"]["SystemResults"]), "rate swap preserves system bins", checks)
    require(rows(native_tables["a"]["StockTotalResults"]) == rows(native_tables["b"]["StockTotalResults"]), "rate swap preserves stock bins", checks)

    reports = {}
    for tag, (_, source_id, _, sxo_sha, closure_sha) in VARIANTS.items():
        reports[tag] = {}
        for selector, (unit, settings_sha, total) in SETTINGS.items():
            run = RUNS / f"a15-two-unit-{tag}-{selector}-20261001-01"
            closure = read(run / "closure.json")
            invocation = read(run / "invocation.json")
            sealed(run, closure, checks)
            require(closure["exit_code"] == 0 and invocation["variant"] == VARIANTS[tag][0] and invocation["selector"] == selector and invocation["source_run_id"] == source_id, f"{tag}/{selector} report provenance", checks)
            require(invocation["source_hashes"] == closure["source_hashes"] and invocation["source_hashes"]["sxo"] == sxo_sha and invocation["source_hashes"]["source_closure"] == closure_sha, f"{tag}/{selector} source seals", checks)
            require(invocation["source_hashes"]["settings"] == settings_sha and sha(RUNS / "report-settings" / f"{selector}.sxs") == settings_sha, f"{tag}/{selector} local settings SHA", checks)
            require(invocation["source_hashes"]["builder"] == sha(HERE / "make_report_settings.py") and invocation["source_hashes"]["runner"] == sha(HERE / "report_existing_sxo_ssh.ps1"), f"{tag}/{selector} report code hashes", checks)
            require(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{tag}/{selector} guarded report context", checks)
            log = (run / "report-export.log").read_text(encoding="utf-8-sig")
            require("Report completed" in log and "Export completed" in log and "Reverting to default settings" not in log and "could not be loaded" not in log, f"{tag}/{selector} loaded settings without fallback", checks)
            tables = {t["name"]: t for t in read(run / "report-raw.json")["report"]["tables"]}
            require(all(name in tables and "SOACC" in [c["name"] for c in tables[name]["columns"]] for name in OPERATION_TABLES), f"{tag}/{selector} four SOACC tables", checks)
            for name in OPERATION_TABLES:
                require(all(r[0] == unit for r in rows(tables[name])), f"{tag}/{selector} {name} unit selector", checks)
            total_acc = [r for r in rows(tables["MissionOperationTotalAccumulated"]) if r[col(tables["MissionOperationTotalAccumulated"], "OPID")] == "KM"]
            total_avg = [r for r in rows(tables["MissionOperationTotal"]) if r[col(tables["MissionOperationTotal"], "OPID")] == "KM"]
            require(len(total_acc) == 1 and total_acc[0][-1] == total, f"{tag}/{selector} total accumulated KM {total}", checks)
            require(len(total_avg) == 1 and abs(total_avg[0][-1] - total / 36) < 1e-6, f"{tag}/{selector} horizon average {total}/36", checks)
            cumulative = [r for r in rows(tables["MissionOperationAccumulated"]) if r[col(tables["MissionOperationAccumulated"], "OPID")] == "KM"]
            active = [r[-1] for r in cumulative if 8 <= r[col(tables["MissionOperationAccumulated"], "STINT")] < 10]
            require(active == ([60, 120, 180, 240] if selector == "all" else [30, 60, 90, 120]), f"{tag}/{selector} four cumulative bins", checks)
            reports[tag][selector] = tables
    for selector in SETTINGS:
        require(all(rows(reports["a"][selector][name]) == rows(reports["b"][selector][name]) for name in OPERATION_TABLES), f"rate swap preserves {selector} operation rows", checks)
    for tag in VARIANTS:
        for name in OPERATION_TABLES:
            if name.endswith("Total") or name.endswith("TotalAccumulated"):
                continue
            all_rows = [r for r in rows(reports[tag]["all"][name]) if r[2] == "KM"]
            a_rows = [r for r in rows(reports[tag]["unit-a"][name]) if r[2] == "KM"]
            b_rows = [r for r in rows(reports[tag]["unit-b"][name]) if r[2] == "KM"]
            require(len(all_rows) == len(a_rows) == len(b_rows) and all(x[3:5] == y[3:5] == z[3:5] and abs(x[-1] - y[-1] - z[-1]) < 1e-6 for x, y, z in zip(all_rows, a_rows, b_rows)), f"{tag} {name} all = unit-a + unit-b", checks)
    result = {
        "schema": "simlox-a15-two-unit-custom-exposure-author-validation/v1",
        "decision": "GO_bounded_two_unit_full_mission_exposure",
        "check_count": len(checks),
        "checks": checks,
        "limits": ["two unit-owned fixed missions, one aircraft per unit", "partial missions, shared formation disaggregation, failures/PM, other seeds, physical kilometres, GUI and cross-engine parity unverified"],
    }
    output = HERE / "author-validation-2026-10-01.json"
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.write_bytes(data)
    print(json.dumps({"decision": result["decision"], "check_count": len(checks), "report_sha256": sha(output)}))


if __name__ == "__main__":
    main()
