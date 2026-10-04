"""Author read-only replay of the bounded K01.var04 native run."""
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated
from build import PARENT, PARENT_SHA

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k01-var04-duration-v100-ssh-20261004-01"
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01/a01-bound-final-20260927-03")
CHILD_SHA = "d1ff80f7e0de8259b6f38b6373c7ad4797d897e17c4397a7060dfbefbeb851dc"
PARENT_CLOSURE_SHA = "7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc, name):
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(found) == 1
    t = found[0]
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def main():
    checks = {}

    def check(label, condition):
        checks[label] = bool(condition)

    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    check("accepted_parent_input_sha", sha(PARENT) == PARENT_SHA)
    check("accepted_parent_closure_sha", sha(PARENT_RUN / "closure.json") == PARENT_CLOSURE_SHA)
    check("child_input_sha", sha(HERE / "native-input.json") == sha(RUN / "input.json") == CHILD_SHA)
    check("invocation_sha", sha(RUN / "invocation.json") == closure["invocation_sha256"])
    check("raw_closure", all((RUN / name).stat().st_size == v["bytes"] and sha(RUN / name) == v["sha256"] for name, v in closure["raw"].items()))
    check("source_hashes_stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    check("session_gui_queue", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    check("five_steps", len(steps) == 5 and [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps))
    check("gui_preserved_each_native_step", all(s["gui_preserved"] for s in steps[:4]))
    check("closure_no_error", closure["error"] is None)
    diagnostics = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("converter_exact", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in diagnostics and re.findall(r"\(warning #(\d+)\)", diagnostics) == ["108", "126"] and not re.search(r"\((?:error|notice) #", diagnostics))
    rt = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    check("roundtrip_13", rt["passed"] and not rt["differences"] and rt["populated_table_count"] == 13 and populated(RUN / "input.json") == {k: populated(RUN / "roundtrip-raw.json")[k] for k in populated(RUN / "input.json")})
    parent, child = json.loads(PARENT.read_bytes()), json.loads((HERE / "native-input.json").read_bytes())
    differences = []
    for old, new in zip(parent["model"]["tables"], child["model"]["tables"]):
        for oi, (old_row, new_row) in enumerate(zip(old["instances"][0]["rows"], new["instances"][0]["rows"])):
            for col, a, b in zip(old["columns"], old_row, new_row):
                if a != b:
                    differences.append((old["name"], oi, col["name"], a, b))
    check("two_cell_diff", differences == [("ProblemDescription", 0, "PDESC", "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence", "K01.var04 v1.0.0 A01-derived three-hour model comparison"), ("MissionType", 0, "DURN", 2.0, 3.0)])
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check("event_timing", len(re.findall(r"Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", log)) == 1 and len(re.findall(r"Time: 8 <BASIC-MISSION.*mission starting, duration: 3", log)) == 1 and len(re.findall(r"Time: 11 <BASIC-MISSION.*mission success:", log)) == 1 and len(re.findall(r"Time: 11 <BASIC-MISSION.*mission completed:", log)) == 1 and not re.search(r"mission (?:cancelled|unfinished)|failure occurs", log, re.I))
    child_report = parse(RUN / "report-raw.json")
    parent_report = parse(PARENT_RUN / "report-raw.json")
    c_names, c_rows = table(child_report, "SystemResults")
    p_names, p_rows = table(parent_report, "SystemResults")
    check("72_half_hour_bins", c_names == p_names and len(c_rows) == len(p_rows) == 72 and all(row[c_names.index("STINT")] == i / 2 and row[c_names.index("ETINT")] == (i + 1) / 2 for i, row in enumerate(c_rows)))
    def integral(rows, field):
        return sum(row[c_names.index(field)] * (row[c_names.index("ETINT")] - row[c_names.index("STINT")]) for row in rows)
    integrals = {key: {"parent": integral(p_rows, key), "child": integral(c_rows, key)} for key in ("NSYRY", "NSYMO", "FTMO")}
    check("report_integrals", integrals == {"NSYRY": {"parent": 33.0, "child": 32.0}, "NSYMO": {"parent": 2.0, "child": 3.0}, "FTMO": {"parent": 2.0, "child": 3.0}})
    changed_bins = [c_rows[i][2] for i in range(72) if c_rows[i] != p_rows[i]]
    check("changed_bins_only_10_to_11", changed_bins == [10, 10.5])
    check("summary_equal", table(parent_report, "ResultSummary") == table(child_report, "ResultSummary") and table(child_report, "ResultSummary")[1] == [[1, 0, 36, 1, 0, 1, 0, 1, 0, 1, 0]])
    check("stock_equal", table(parent_report, "StockTotalResults") == table(child_report, "StockTotalResults"))
    result = {"schema": "simlox-k01-var04-author-validation/v1", "case_id": "K01", "variant_id": "K01.var04", "run_id": RUN.name, "passed": all(checks.values()), "checks": checks, "passed_count": sum(checks.values()), "check_count": len(checks), "parent_child_differences": differences, "integrals_hours": integrals, "changed_system_bin_starts": changed_bins, "raw_files_sealed": len(closure["raw"]), "scope": "CLI-visible A01-derived model source difference only"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
