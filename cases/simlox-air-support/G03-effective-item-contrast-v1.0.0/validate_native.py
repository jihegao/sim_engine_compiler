"""Author replay of four sealed G03 effective-item native contrasts."""
import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json, populated
from build import D01, D01_SHA, HERE, PARENTS, VARIANTS

EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, label, checks):
    if not ok:
        raise AssertionError(label)
    checks.append(label)


def values(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def col(table, name):
    return [x["name"] for x in table["columns"]].index(name)


def main():
    checks = []
    contract = native_json(HERE / "contract.json")
    require(sha(D01) == D01_SHA == contract["parents"]["repair_method"]["sha256"], "accepted D01 method", checks)
    require(sha(EXE) == EXE_SHA, "installed executable", checks)
    reports = {}
    for variant, (branch, sid, failing_item) in VARIANTS.items():
        parent, parent_sha = PARENTS[branch]
        require(sha(parent) == parent_sha == contract["parents"][branch]["sha256"], f"{variant} accepted G03 parent", checks)
        run = HERE / "runs" / f"g03-effective-{variant}-v100-20261001-01"
        source = HERE / f"{variant}-input.json"
        require(sha(source) == sha(run / "input.json") == contract["inputs_sha256"][variant], f"{variant} frozen source", checks)
        invocation, closure = native_json(run / "invocation.json"), native_json(run / "closure.json")
        require(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} closure", checks)
        require(all((run / name).is_file() and (run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"] for name, record in closure["raw"].items()), f"{variant} raw hash closure", checks)
        require(closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["repair_method"] == D01_SHA and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{variant} source stable", checks)
        require(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} SSH mutex GUI", checks)
        steps = native_json(run / "steps.json")
        require([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), f"{variant} five native steps", checks)
        source_tables = populated(native_json(source))
        exported = populated(native_json(run / "roundtrip-raw.json"))
        require(len(source_tables) == 18 and all(exported.get(name) == table for name, table in source_tables.items()) and native_json(run / "roundtrip-validation.json")["passed"], f"{variant} 18-table roundtrip", checks)
        model = {table["name"]: table for table in native_json(source)["model"]["tables"]}
        require(values(model["SystemDeployment"])[0][0] == sid and all(row[3] == (300000 if row[0] == failing_item else 0) for row in values(model["Item"])), f"{variant} deployment and item rate", checks)
        require("Input conversion completed. Errors: 0" in (run / "run.log").read_text(encoding="utf-8-sig"), f"{variant} zero conversion errors", checks)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        require(f"mission allocates system: <{sid}," in log and log.count("mission starting, duration: 2") == 3, f"{variant} three missions on chosen SID", checks)
        report = {table["name"]: table for table in native_json(run / "report-raw.json")["report"]["tables"]}
        system, stock, summary = report["SystemResults"], report["StockTotalResults"], report["ResultSummary"]
        sr, st = values(system), values(stock)
        require(len(sr) == len(st) == 72 and values(summary)[0][col(summary, "RTIUP")] == 36 and sr[-1][col(system, "NSYRY")] == 1, f"{variant} 36-hour terminal ledgers", checks)
        require(sum(row[col(stock, "NBO")] for row in st) == 0, f"{variant} no backorder", checks)
        clocks = [line for line in log.splitlines() if "Next random failure will occur" in line]
        if variant == "exclude-base":
            require(clocks and all("1e+010" in line for line in clocks), "exclude has no finite failure clock", checks)
            require("subitem failed:" not in log and "Item demand arrives" not in log and "Take replacement item" not in log, "exclude no item failure/demand", checks)
            require(all(sum(row[col(table, key)] for row in values(table)) == 0 for table, key in ((system, "NFAIL"), (system, "NREPT"), (stock, "NDF"))) and values(summary)[0][col(summary, "MSUF")] == 1, "exclude zero metrics and three successes", checks)
        else:
            require(any("9.8829" in line and "Next random failure" in line for line in clocks), f"{variant} finite first failure clock", checks)
            require(f"subitem failed: <{failing_item}," in log and f"connection path: {sid} - {sid} - {failing_item}" in log, f"{variant} effective item identity/path", checks)
            require(f"Item demand arrives from pos <{sid}," in log and f"Take replacement item <{failing_item}," in log and f"Finished repair of item <{failing_item}," in log, f"{variant} physical stock and repair chain", checks)
            require(all(sum(row[col(table, key)] for row in values(table)) == 1 for table, key in ((system, "NFAIL"), (system, "NREPT"), (stock, "NDF"))) and abs(values(summary)[0][col(summary, "MSUF")] - 2 / 3) < 1e-6, f"{variant} one failure/repair/demand and two successes", checks)
        reports[variant] = (sr, st, values(summary))
    require(reports["base-control"] == reports["add-inherited"] == reports["add-extra"], "positive branches identical aggregate ledgers", checks)
    result = {"schema": "simlox-g03-effective-item-author-validation/v1", "decision": "GO_bounded_effective_BSID_item_propagation", "check_count": len(checks), "checks": checks, "limits": ["one seed/rate and three missions", "exclusion supported by no finite native failure clock plus paired positive control, not by failure absence alone", "GUI-only behavior and cross-engine parity unverified", "A16 CBSID is separate"]}
    target = HERE / "author-validation-2026-10-01.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "check_count": len(checks), "sha256": sha(target)}))


if __name__ == "__main__":
    main()
