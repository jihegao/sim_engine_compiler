"""Author replay of sealed G03 variant-only native observations."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json, populated
from build import HERE, PARENT, PARENT_SHA

EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, label, checks):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def values(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def column(table, name):
    return [x["name"] for x in table["columns"]].index(name)


def main():
    checks = []
    contract = native_json(HERE / "contract.json")
    require(sha(PARENT) == PARENT_SHA == contract["parent_source_sha256"], "accepted A01 parent", checks)
    require(sha(EXE) == EXE_SHA, "installed executable", checks)
    for variant in ("add", "exclude"):
        source = HERE / f"{variant}-input.json"
        run = HERE / "runs" / f"g03-{variant}-v101-20261001-01"
        expected_sha = contract["variants"][variant]["input_sha256"]
        require(sha(source) == sha(run / "input.json") == expected_sha, f"{variant} source fingerprint", checks)
        invocation, closure = native_json(run / "invocation.json"), native_json(run / "closure.json")
        require(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} sealed invocation", checks)
        require(all((run / name).is_file() and (run / name).stat().st_size == value["bytes"] and sha(run / name) == value["sha256"] for name, value in closure["raw"].items()), f"{variant} sealed raw files", checks)
        require(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} SSH queue GUI provenance", checks)
        require(closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{variant} stable source hashes", checks)
        steps = native_json(run / "steps.json")
        require([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), f"{variant} five guarded native steps", checks)
        roundtrip = native_json(run / "roundtrip-validation.json")
        require(roundtrip["passed"] and not roundtrip["differences"], f"{variant} native checker", checks)
        original = populated(native_json(source))
        exported = populated(native_json(run / "roundtrip-raw.json"))
        require(all(exported.get(name) == value for name, value in original.items()), f"{variant} direct input/export equality", checks)
        source_tables = {table["name"]: table for table in native_json(source)["model"]["tables"]}
        sid = contract["variants"][variant]["variant_sid"]
        require(values(source_tables["System"])[1][9] == "TEACH-AIR-01" and values(source_tables["System"])[1][7] is None and values(source_tables["SystemDeployment"])[0][0] == sid, f"{variant} BSID and variant-only deployment", checks)
        structure = values(source_tables["ItemStructure"])
        require(structure[0][:3] == ["TEACH-LRU-BASE", "TEACH-AIR-01", 1] and structure[1][:3] == (["TEACH-LRU-ADD", sid, 1] if variant == "add" else ["TEACH-LRU-BASE", sid, 0]), f"{variant} exact add/exclude rows", checks)
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Input conversion completed. Errors: 0" in run_log, f"{variant} zero conversion errors", checks)
        event_log = (run / "model.log").read_text(encoding="utf-8-sig")
        require(f"Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <{sid},0>" in event_log and f"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <{sid},0>" in event_log and f"Time: 10 <{sid},BASE-01,0> System arrives <{sid},0>, mission success" in event_log, f"{variant} individual variant timeline", checks)
        report = {table["name"]: table for table in native_json(run / "report-raw.json")["report"]["tables"]}
        system, stock, summary = report["SystemResults"], report["StockTotalResults"], report["ResultSummary"]
        sr, st = values(system), values(stock)
        require(len(sr) == len(st) == 72 and values(summary)[0][column(summary, "RTIUP")] == 36, f"{variant} 36-hour report bins", checks)
        require(sr[-1][column(system, "NSYRY")] == 1 and all(row[column(system, "NFAIL")] == row[column(system, "NREPT")] == row[column(system, "NPMT")] == 0 for row in sr), f"{variant} terminal ready and zero failure/maintenance", checks)
        require(all(row[column(stock, "NBO")] == row[column(stock, "NDF")] == row[column(stock, "NDD")] == 0 for row in st), f"{variant} zero stock activity", checks)
        require(values(summary)[0][column(summary, "MTMF")] == 1, f"{variant} completed mission time factor", checks)
    result = {"schema": "simlox-g03-variant-structure-v101-author-validation/v1", "decision": "GO_bounded_BSID_source_roundtrip_and_variant_operation", "check_count": len(checks), "checks": checks, "limits": ["effective inherited item composition not exposed in default report", "failure/repair/utilization aggregation by item not exercised", "G03.var03 and var04 remain unpublished", "GUI-only behavior unverified"]}
    target = HERE / "author-validation-2026-10-01.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "check_count": len(checks), "sha256": sha(target)}))


if __name__ == "__main__":
    main()
