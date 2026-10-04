"""Independent, read-only F04.var03 System-window replay.

Uses frozen JSON and native raw files directly. Does not import the case builder,
checker, or author validator. The sole output is the adjacent verdict JSON.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "F04-var02-stochastic-43day-v1.0.0"
EXCLUDED = ROOT / "F04-var03-first-cycle-window-v1.0.0"
RUN = CASE / "runs/f04-var03-system-window-v101-ssh-20261004-01"
PARENT_RUN = PARENT / "runs/f04-var02-stochastic-v100-repeat-a-ssh-20261004-01"
EXCLUDED_RUN = EXCLUDED / "runs/f04-var03-first-cycle-v100-ssh-20261004-01"
OUT = Path(__file__).with_name("independent-verdict.json")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path, *, native_report: bool = False):
    raw = path.read_text(encoding="utf-8-sig")
    if native_report:
        # The native default exporter appends one comma before the closing list.
        # The replication exporter is strict JSON and is never modified here.
        raw = re.sub(r",(\s*\]\s*\}\s*\}\s*)$", r"\1", raw)
    return json.loads(raw)


def tables(document):
    return {t["name"]: t for t in document["model"]["tables"]}


def report_tables(document):
    return {t["name"]: t for t in document["report"]["tables"]}


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r, strict=True)) for r in rows(table)]


class Audit:
    def __init__(self):
        self.total = 0
        self.failures = []

    def check(self, condition, label):
        self.total += 1
        if not condition:
            self.failures.append(label)

    def equal(self, actual, expected, label):
        self.check(actual == expected, label)

    def close(self, actual, expected, label, tolerance=2e-6):
        self.check(math.isclose(actual, expected, abs_tol=tolerance, rel_tol=tolerance), label)


def main():
    a = Audit()
    contract = read(CASE / "contract.json")
    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    steps = read(RUN / "steps.json")
    parent = contract["accepted_parent"]
    excluded = contract["excluded_diagnostic"]
    current = read(CASE / "native-input.json")
    previous = read(PARENT / "native-input.json")
    older = read(EXCLUDED / "native-input.json")

    pins = {
        CASE / "native-input.json": contract["input_sha256"],
        CASE / "exact-diff.json": contract["exact_diff_sha256"],
        PARENT / "native-input.json": parent["input_sha256"],
        PARENT_RUN / "closure.json": parent["closure_sha256"],
        PARENT / "cli-scope-signoff-2026-10-04.md": parent["signoff_sha256"],
        PARENT_RUN / "report-raw.json": parent["default_report_sha256"],
        PARENT_RUN / "replication-report-raw.json": parent["replication_report_sha256"],
        EXCLUDED / "native-input.json": excluded["input_sha256"],
        EXCLUDED_RUN / "closure.json": excluded["closure_sha256"],
    }
    for path, expected in pins.items():
        a.equal(sha(path), expected, f"lineage SHA: {path.name} ({path.parent.name})")
    a.equal(sha(CASE / "contract.json"), closure["source_hashes_before"]["contract"], "contract SHA in closure")
    a.equal(sha(RUN / "closure.json"), "5a520ba79c043b72e0461fc73325ead04e0d2c0f7c3ff5fa7a44962fc985875d", "native closure SHA")
    for name in ["build.py", "describe_diff.py", "make_report_settings.py", "check_roundtrip.py", "run_native_ssh.ps1"]:
        a.equal(sha(CASE / name), closure["source_hashes_before"][name], f"current frozen source {name}")

    pt, ct, xt = tables(previous), tables(current), tables(older)
    a.equal(set(ct), set(pt), "all 33 source table names")
    changes = []
    for name in sorted(set(ct) & set(pt)):
        ptable, ctable = pt[name], ct[name]
        a.equal([c["name"] for c in ctable["columns"]], [c["name"] for c in ptable["columns"]], f"source columns {name}")
        p_rows, c_rows = rows(ptable), rows(ctable)
        a.equal(len(c_rows), len(p_rows), f"source row count {name}")
        for rowno, (pr, cr) in enumerate(zip(p_rows, c_rows), 1):
            for colno, (pv, cv) in enumerate(zip(pr, cr)):
                if pv != cv:
                    changes.append((name, rowno, ctable["columns"][colno]["name"], pv, cv))
    diff = read(CASE / "exact-diff.json")
    declared = [(d["table"], d["row"], d["column"], d["from"], d["to"]) for d in diff["changed_cells"]]
    a.equal(changes, declared, "exact two-cell source delta matches frozen diff")
    a.equal(len(changes), 2, "two changed source cells")
    a.equal(records(ct["Control"])[0]["SIMPE"], 1032, "simulation remains 1032 h")
    a.equal(records(ct["Control"])[0]["RCEND"], 1032, "Control report window remains 1032 h")
    rc = records(ct["ResultCollection"])
    a.equal([(r["RTYPE"], r["RCEND"]) for r in rc], [("MISSION", 1032), ("SYSTEM", 48)], "only System collection ends at 48 h")
    a.equal(records(xt["Control"])[0]["RCEND"], 48, "excluded Control window was 48 h")

    a.equal(closure["error"], None, "closure error null")
    a.equal(closure["run_id"], RUN.name, "closure run ID")
    a.equal(closure["source_hashes_before"], closure["source_hashes_after"], "source seal before and after identical")
    a.equal(sha(RUN / "invocation.json"), closure["invocation_sha256"], "invocation SHA")
    a.equal(invocation["source_hashes_before"], closure["source_hashes_before"], "invocation source seal")
    a.equal(invocation["session_id"], 0, "session zero")
    a.equal(invocation["execution_mode"], "ssh_cli_v1", "guarded SSH CLI execution")
    a.equal(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", "serial native queue mutex")
    a.check("sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]], "SSH daemon ancestor")
    a.equal(invocation["gui"]["pid"], 13340, "preserved GUI PID")
    a.equal(invocation["gui"]["session_id"], 1, "GUI remains in interactive session")
    a.equal(len(closure["raw"]), 14, "fourteen raw seals")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        a.equal(path.stat().st_size, seal["bytes"], f"raw size {name}")
        a.equal(sha(path), seal["sha256"], f"raw SHA {name}")
    a.equal([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "replication_report", "check_import_export"], "six guarded steps")
    for step in steps:
        a.equal(step["exit_code"], 0, f"step exit {step['name']}")
        if step["name"] != "check_import_export":
            a.equal(step["gui_preserved"], True, f"GUI preservation {step['name']}")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    a.check(bool(re.search(r"Errors:\s*0,\s*Warnings:\s*1,\s*Notes:\s*0", log)), "exact converter totals")
    a.check("#108" in log, "reviewed warning #108")
    a.equal((RUN / "model.log").read_bytes(), (PARENT_RUN / "model.log").read_bytes(), "first-rep event log byte identity")

    exported = tables(read(RUN / "roundtrip-raw.json"))
    populated = 0
    for name, source in ct.items():
        if not rows(source):
            continue
        populated += 1
        a.check(name in exported, f"roundtrip table {name}")
        if name not in exported:
            continue
        actual = exported[name]
        a.equal(actual["columns"], source["columns"], f"roundtrip columns {name}")
        a.equal(actual["instances"], source["instances"], f"roundtrip rows {name}")
    a.equal(populated, 31, "31 populated authored tables")
    a.equal(read(RUN / "roundtrip-validation.json")["passed"], True, "author checker status corroborated")

    default = report_tables(read(RUN / "report-raw.json", native_report=True))
    parent_default = report_tables(read(PARENT_RUN / "report-raw.json", native_report=True))
    extended = report_tables(read(RUN / "replication-report-raw.json"))
    parent_extended = report_tables(read(PARENT_RUN / "replication-report-raw.json"))
    excluded_default = report_tables(read(EXCLUDED_RUN / "report-raw.json", native_report=True))
    for label, child, old in [("default", default, parent_default), ("OUTRP", extended, parent_extended)]:
        for table_name in ["ResultSummary", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]:
            a.equal(child[table_name]["columns"], old[table_name]["columns"], f"{label} {table_name} columns")
            new_rows, old_rows = rows(child[table_name]), rows(old[table_name])
            a.equal(len(new_rows), len(old_rows), f"{label} {table_name} row count")
            for i, (new_row, old_row) in enumerate(zip(new_rows, old_rows), 1):
                a.equal(new_row, old_row, f"{label} {table_name} row {i}")
        system, original = child["SystemResults"], old["SystemResults"]
        a.equal(system["columns"], original["columns"], f"{label} SystemResults columns")
        short_rows, full_rows = rows(system), rows(original)
        a.equal(len(short_rows), 96, f"{label} 96 System bins")
        a.equal(len(full_rows), 2064, f"{label} 2064 parent System bins")
        for i, (new_row, old_row) in enumerate(zip(short_rows, full_rows), 1):
            a.equal(new_row, old_row, f"{label} System prefix bin {i}")
    a.equal(rows(extended["Replications"]), rows(parent_extended["Replications"]), "128 full-horizon Replications exact")
    a.equal(len(rows(extended["Replications"])), 128, "128 Replications rows")
    a.equal(len({r["REPNO"] for r in records(extended["Replications"])}), 128, "128 unique replication IDs")
    a.check(rows(excluded_default["ResultSummary"]) != rows(parent_default["ResultSummary"]), "excluded all-window summary changed")
    for name in ["SystemResults", "StockTotalResults", "ResourceResults"]:
        a.equal(len(rows(excluded_default[name])), 96, f"excluded {name} truncated")

    total = records(extended["SystemResultsReplicationTotal"])
    timed = records(extended["SystemResultsReplication"])
    a.equal(len(total), 256, "256 two-unit System TOTAL rows")
    a.equal(len(timed), 256, "256 timed per-unit System rows")
    key = lambda r: (r["REPLID"], r["UNID"], r["SID"])
    total_map = {key(r): r for r in total}
    timed_map = {key(r): r for r in timed}
    a.equal(set(total_map), set(timed_map), "timed and TOTAL per-rep keys")
    a.equal(len(total_map), 256, "no duplicate System per-rep keys")
    a.equal({r["REPLID"] for r in total}, set(range(1, 129)), "per-rep IDs 1 through 128")
    a.equal({r["UNID"] for r in total}, {"TEACH-UNIT", "TEACH-UNIT-2"}, "two unit totals")
    for row in timed:
        k = key(row)
        a.equal((row["STINT"], row["ETINT"]), (0, 48), f"per-rep short horizon {k}")
        for field in ["STACC", "NFAIL", "NPMT", "NPMS", "NPSTA", "NPSUC", "NREPT"]:
            a.equal(row[field], total_map[k][field], f"timed/TOTAL {field} {k}")
    short = records(extended["SystemResults"])
    for i, row in enumerate(short):
        a.equal((row["STINT"], row["ETINT"]), (i * .5, (i + 1) * .5), f"half-hour System bin {i}")
    for field in ["STACC", "NFAIL", "NPMT", "NPMS", "NPSTA", "NPSUC", "NREPT"]:
        per_rep_mean = sum(r[field] for r in total) / 128
        aggregate = sum(r[field] * (.5 if field == "STACC" else 1) for r in short)
        expected = per_rep_mean * (48 if field == "STACC" else 1)
        a.close(aggregate, expected, f"per-rep/aggregate reconciliation {field}")

    result = {
        "schema": "f04-var03-independent-readonly-replay/v1",
        "passed": not a.failures,
        "verdict": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks_total": a.total,
        "checks_passed": a.total - len(a.failures),
        "failures": a.failures,
        "fingerprints": {
            "input_sha256": sha(CASE / "native-input.json"),
            "contract_sha256": sha(CASE / "contract.json"),
            "diff_sha256": sha(CASE / "exact-diff.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "parent_closure_sha256": sha(PARENT_RUN / "closure.json"),
            "excluded_closure_sha256": sha(EXCLUDED_RUN / "closure.json"),
        },
        "observations": {
            "system_bins": len(rows(extended["SystemResults"])),
            "parent_system_bins": len(rows(parent_extended["SystemResults"])),
            "stock_bins": len(rows(extended["StockTotalResults"])),
            "resource_bins": len(rows(extended["ResourceResults"])),
            "replications": len(rows(extended["Replications"])),
            "system_unit_replication_rows": len(total),
            "mean_first_48h_aircraft_hours": sum(r["STACC"] * .5 for r in short),
            "mean_first_48h_failures": sum(r["NFAIL"] for r in short),
            "excluded_all_entity_window_changes_summary": rows(excluded_default["ResultSummary"]) != rows(parent_default["ResultSummary"]),
        },
        "limits": [
            "System collection only ends at 48 h; simulation and mission, stock, and resource windows remain 1032 h.",
            "System per-rep TOTAL metrics use the shorter horizon and must not be equated with parent totals.",
            "Only the first replication has an event log; this is a same-seed, one-engine comparison.",
            "The excluded v1.0.0 all-entity window diagnostic is provenance, not accepted evidence.",
        ],
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {result['checks_passed']}/{result['checks_total']} checks")
    for failure in a.failures[:20]:
        print("FAIL:", failure)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
