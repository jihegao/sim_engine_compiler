"""Author read-only validation for accepted named and excluded inactive K02 probes."""
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, tables

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "K01-var04-parent-child-model-diff-v1.0.0" / "runs" / "k01-var04-duration-v100-ssh-20261004-01"
V100 = ROOT / "K02-var01-json-structure-v1.0.0" / "runs"
RUNS = {
    "named": HERE / "runs" / "k02-var01-named-v101-ssh-20261004-01",
    "inactive2": HERE / "runs" / "k02-var01-inactive2-v101-ssh-20261004-01",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_table(doc, name):
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]["instances"][0]["rows"]


def main():
    checks = {}
    def check(name, value):
        checks[name] = bool(value)

    parent_report = parse(PARENT / "report-raw.json")
    parent_log = (PARENT / "model.log").read_bytes()
    parent_tables = tables(ROOT / "K01-var04-parent-child-model-diff-v1.0.0" / "native-input.json")
    observations = {}
    for arm, run in RUNS.items():
        closure = load(run / "closure.json")
        inv = load(run / "invocation.json")
        steps = load(run / "steps.json")
        roundtrip = load(run / "roundtrip-validation.json")
        source = tables(HERE / f"{arm}-input.json")
        export = tables(run / "roundtrip-raw.json")
        report = parse(run / "report-raw.json")
        prefix = f"{arm}_"
        check(prefix + "source_input_sha", sha(HERE / f"{arm}-input.json") == sha(run / "input.json") == closure["source_hashes_before"][f"{arm}_input"])
        check(prefix + "source_stability", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        check(prefix + "invocation_sha", sha(run / "invocation.json") == closure["invocation_sha256"])
        check(prefix + "raw_sha_closure", len(closure["raw"]) == 12 and all((run / name).stat().st_size == item["bytes"] and sha(run / name) == item["sha256"] for name, item in closure["raw"].items()))
        check(prefix + "session_gui_mutex", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        check(prefix + "native_steps", [s["name"] for s in steps[:4]] == ["import", "export", "calc", "jsonreport"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps[:4]))
        diagnostics = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "converter", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in diagnostics and re.findall(r"\(warning #(\d+)\)", diagnostics) == ["108", "126"] and not re.search(r"\((?:error|notice) #", diagnostics))
        check(prefix + "parent_log_equal", (run / "model.log").read_bytes() == parent_log)
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(prefix + name + "_equal", report_table(report, name) == report_table(parent_report, name))
        c_system = report_table(report, "SystemResults")
        check(prefix + "72_bins", len(c_system) == 72 and c_system[-1][2:4] == [35.5, 36])
        check(prefix + "other_source_tables_same", all(source[name] == old for name, old in parent_tables.items() if name not in ("ProblemDescription", "Station")))
        check(prefix + "authored_column_types_same", all(source[name]["columns"] == old["columns"] for name, old in parent_tables.items()))
        observations[arm] = {"closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"]), "roundtrip_passed": roundtrip["passed"], "roundtrip_differences": roundtrip["differences"], "station_export_instances": export["Station"]["instances"]}
        if arm == "named":
            station = export["Station"]["instances"]
            check("named_exact_two_authored_instances", station[1:] == source["Station"]["instances"] and [x["instance_name"] for x in station[1:]] == ["K02-BASE", "K02-AUX"])
            check("named_only_empty_default_canonicalization", len(station) == 3 and station[0] == {"instance_name": "", "rows": [[None] * 21]})
            check("named_roundtrip_gate", roundtrip["passed"] and not roundtrip["differences"] and roundtrip["authored_row_table_count"] == 13 and roundtrip["double_precision_binary64_preserved"])
            check("named_complete", closure["error"] is None and len(steps) == 5 and steps[4]["status"] == "completed" and steps[4]["exit_code"] == 0)
        else:
            station = export["Station"]["instances"]
            check("inactive2_targeted_second_row", len(station) == 1 and station[0]["rows"] == [source["Station"]["instances"][0]["rows"][0], [None] * 21])
            check("inactive2_marker_lost", "inactive_rows" not in station[0])
            check("inactive2_roundtrip_no_go", not roundtrip["passed"] and roundtrip["differences"] == ["authored instances/rows/inactive metadata differ: Station"] and closure["error"] == "roundtrip checker exit=1")
    old = {}
    for arm, name in (("inactive_index1", "k02-var01-inactive-v100-ssh-20261004-01"), ("named_strict", "k02-var01-named-v100-ssh-20261004-01")):
        run = V100 / name
        closure = load(run / "closure.json")
        check(arm + "_closure", all((run / n).stat().st_size == v["bytes"] and sha(run / n) == v["sha256"] for n, v in closure["raw"].items()))
        old[arm] = {"run_id": name, "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"])}
    result = {"schema": "simlox-k02-var01-author-validation/v1", "case_id": "K02", "variant_id": "K02.var01", "version": "1.0.1", "accepted_arm": "named", "excluded_arms": ["inactive_index1_v100", "named_strict_v100", "inactive2_v101"], "passed": all(checks.values()), "passed_count": sum(checks.values()), "check_count": len(checks), "checks": checks, "v101_observations": observations, "v100_diagnostics": old, "limits": ["Named Station instances on one A01-derived model only; native export adds one blank default instance.", "Inactive rows are lossy through this JSON import/export path; no lossless inactive-row claim.", "GUI views/templates, other table instances and full K02 remain unverified."]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
